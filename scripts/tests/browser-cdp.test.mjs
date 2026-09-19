import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, mkdir, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {runInNewContext} from 'node:vm';
import {capture as rawCapture, dailyEndpoint, validateBudget} from '../browser_cdp.mjs';

const budgetFor = (n, extra={}) => ({version:1,max_rows:25,max_pages:2,used_rows:0,used_pages:[],
  stages:Array.from({length:n+1},()=>({row_selector:'.observed-job-card',page:1,max_rows:0})),...extra});
const capture = options => rawCapture({...options, ...(!('budget' in options) && (options.steps?.length || options.clickText) ?
  {budget:budgetFor(options.steps?.length || 1)} : {})});

let fixtureId = 0;
function fixture({status=200, navigationError=false, pageReadyState='complete', pageRefusal=false, pageTextReady=true, readyAfterWait=false, textAfterWait=false, revealNodeExists=true, textAfterReveal=false, refuseAfterClick=false, catalogCounts=[], failClick=0}={}) {
  const commands=[];
  let clicks=0;
  const target=`owned-${++fixtureId}`, session=`session-${fixtureId}`;
  class Socket extends EventTarget {
    constructor() {super();this.readyState=1;queueMicrotask(()=>this.dispatchEvent(new Event('open')));}
    send(raw) {
      const c=JSON.parse(raw);commands.push(c);
      const emit=data=>this.dispatchEvent(new MessageEvent('message',{data:JSON.stringify(data)}));
      queueMicrotask(()=>{
        let result={};
        if(c.method==='Target.createTarget') result={targetId:target};
        if(c.method==='Target.attachToTarget') result={sessionId:session};
        if(c.method==='Page.navigate') {
          emit({sessionId:session,method:'Network.responseReceived',params:{frameId:'frame',type:'Document',response:{url:'https://example.com/',status}}});
          result=navigationError?{errorText:'net::ERR_FAILED'}:{frameId:'frame'};
        }
        if(c.method==='Runtime.evaluate') result={result:{value:c.params.expression==='document.readyState'?(Array.isArray(pageReadyState)?pageReadyState.shift() || 'complete':pageReadyState):c.params.expression.startsWith('Boolean(') && (c.params.expression.includes('.includes(') || c.params.expression.startsWith('Boolean((() =>'))?(Array.isArray(pageTextReady)?pageTextReady.shift():pageTextReady):c.params.expression.startsWith('Boolean(')?pageRefusal:{url:'https://example.com/',title:'Fixture',text:'Visible job description',links:[]}}};
        if(c.method==='Runtime.evaluate' && c.params.expression.startsWith('Boolean(\n')) {
          if(readyAfterWait) pageReadyState='complete';
          if(textAfterWait) pageTextReady=true;
        }
        if(c.method==='Runtime.evaluate' && c.params.expression.startsWith('Boolean(document.querySelector')) result={result:{value:revealNodeExists}};
        if(c.method==='Runtime.evaluate' && c.params.expression.includes('.scrollIntoView(')) {
          result={result:{value:revealNodeExists}};
          if(textAfterReveal) pageTextReady=true;
        }
        if(c.method==='Runtime.evaluate' && c.params.expression.includes('node.click()')) {
          clicks++;
          result={result:{value:{performed:true,label:'Observed control',action:'navigate'}}};
          if(clicks === failClick) result={result:{value:{error:'Control disappeared'}}};
          if(refuseAfterClick) pageRefusal=true;
        }
        if(c.method==='Runtime.evaluate' && c.params.expression.includes('snapshot.catalog_rows')) {
          const catalog_rows=Array.from({length:catalogCounts[clicks] || 0},(_,i)=>({source_id:`Job ${clicks}-${i}`,title:`Job ${clicks}-${i}`,raw_text:`Job ${clicks}-${i}`,url:'https://example.com/'}));
          result={result:{value:{url:'https://example.com/',title:'Fixture',text:catalog_rows.map(r=>r.raw_text).join('\n') || 'Visible job description',links:[],catalog_rows}}};
        }
        if(c.method==='Target.closeTarget') result={success:true};
        emit({id:c.id,result});
      });
    }
    close(){this.readyState=3;this.dispatchEvent(new Event('close'));}
  }
  return {Socket,commands,target,session};
}

test('capture retains refusal status and closes only its own tab',async()=>{
  const {Socket,commands,target,session}=fixture({status:403});
  const result=await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',settleMs:0,WebSocketImpl:Socket});
  assert.equal(result.http_status,403);
  assert.equal(result.capture.backend,'builtin-cdp');
  assert.deepEqual(commands.filter(c=>c.method==='Target.closeTarget').map(c=>c.params.targetId),[target]);
  assert.equal(commands.some(c=>c.method==='Target.getTargets'),false);
  assert.ok(commands.filter(c=>/^(Page|Runtime|Network)\./.test(c.method)).every(c=>c.sessionId===session));
  assert.equal(result.capture.trace.at(-1).method,'Target.closeTarget');
});

test('a navigation failure still closes the created tab',async()=>{
  const {Socket,commands,target}=fixture({navigationError:true});
  await assert.rejects(capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',settleMs:0,WebSocketImpl:Socket}),/Navigation failed/);
  assert.equal(commands.at(-1).method,'Target.closeTarget');
  assert.equal(commands.at(-1).params.targetId,target);
});

test('a page that never finishes loading retains its DOM after three increasing waits',async()=>{
  const {Socket,commands,target}=fixture({pageReadyState:'interactive'});
  const result=await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',timeoutMs:5,settleMs:0,WebSocketImpl:Socket});
  assert.equal(result.load_timed_out,true);
  assert.equal(result.http_status,200);
  assert.deepEqual(result.render_wait_budgets_ms,[5,10,20]);
  assert.equal(result.text,'Visible job description');
  assert.deepEqual(commands.filter(c=>c.method==='Target.closeTarget').map(c=>c.params.targetId),[target]);
  assert.equal(commands.filter(c=>c.method==='Page.navigate').length,1);
});

test('a later render succeeds without navigating again',async()=>{
  const {Socket,commands}=fixture({pageReadyState:'loading',readyAfterWait:true});
  const result=await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',waitStagesMs:[2,4,8],settleMs:0,WebSocketImpl:Socket});
  assert.equal(result.load_timed_out,false);
  assert.deepEqual(result.render_wait_budgets_ms,[2,4]);
  assert.equal(commands.filter(c=>c.method==='Page.navigate').length,1);
});

test('document complete still waits for the requested rendered description',async()=>{
  const {Socket,commands}=fixture({pageTextReady:false,textAfterWait:true});
  const result=await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',waitStagesMs:[2,4,8],waitForText:'About the job',settleMs:0,WebSocketImpl:Socket});
  assert.equal(result.load_timed_out,false);
  assert.equal(result.wait_for_text,'About the job');
  assert.deepEqual(result.render_wait_budgets_ms,[2,4]);
  assert.equal(commands.filter(c=>c.method==='Page.navigate').length,1);
});

test('revealing an observed lazy node activates only the owned tab and waits for its description',async()=>{
  const {Socket,commands,target,session}=fixture({pageTextReady:false,textAfterReveal:true});
  const result=await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',waitStagesMs:[2,4,8],waitForText:'About the job',revealSelector:'#job-description',settleMs:0,WebSocketImpl:Socket});
  assert.equal(result.load_timed_out,false);
  assert.deepEqual(result.render_wait_budgets_ms,[2,4]);
  assert.equal(result.reveal.performed,true);
  assert.equal(result.reveal.after_wait_stage,1);
  assert.deepEqual(commands.filter(c=>c.method==='Target.activateTarget').map(c=>c.params.targetId),[target]);
  const scrolls=commands.filter(c=>c.params.expression?.includes('.scrollIntoView('));
  assert.equal(scrolls.length,1);
  assert.equal(scrolls[0].sessionId,session);
  assert.equal(commands.filter(c=>c.method==='Page.navigate').length,1);
  assert.deepEqual(commands.filter(c=>c.method==='Target.closeTarget').map(c=>c.params.targetId),[target]);
});

test('a missing reveal node errors without activation or scrolling and closes its tab',async()=>{
  const {Socket,commands,target}=fixture({pageTextReady:false,revealNodeExists:false});
  await assert.rejects(capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',waitStagesMs:[2,4,8],waitForText:'About the job',revealSelector:'#missing',settleMs:0,WebSocketImpl:Socket}),/Reveal selector not found/);
  assert.equal(commands.some(c=>c.method==='Target.activateTarget' || c.params.expression?.includes('.scrollIntoView(')),false);
  assert.deepEqual(commands.filter(c=>c.method==='Target.closeTarget').map(c=>c.params.targetId),[target]);
});

test('an unfilled revealed node retains the timeout without repeated scrolling',async()=>{
  const {Socket,commands,target}=fixture({pageTextReady:false});
  const result=await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',waitStagesMs:[2,4,8],waitForText:'About the job',revealSelector:'#job-description',settleMs:0,WebSocketImpl:Socket});
  assert.equal(result.load_timed_out,true);
  assert.deepEqual(result.render_wait_budgets_ms,[2,4,8]);
  assert.equal(commands.filter(c=>c.method==='Target.activateTarget').length,1);
  assert.equal(commands.filter(c=>c.params.expression?.includes('.scrollIntoView(')).length,1);
  assert.deepEqual(commands.filter(c=>c.method==='Target.closeTarget').map(c=>c.params.targetId),[target]);
});

test('default waiting and an already readable page never activate a tab',async()=>{
  for(const options of [{pageTextReady:false},{pageTextReady:true,revealSelector:'#job-description'}]) {
    const {Socket,commands}=fixture(options);
    const result=await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',waitStagesMs:[2,4,8],waitForText:'About the job',revealSelector:options.revealSelector,settleMs:0,WebSocketImpl:Socket});
    assert.equal(commands.some(c=>c.method==='Target.activateTarget' || c.params.expression?.includes('.scrollIntoView(')),false);
    assert.equal(result.load_timed_out,!options.pageTextReady);
  }
});

test('a refusal prevents revealing a node',async()=>{
  for(const refusal of [{status:403},{pageRefusal:true}]) {
    const {Socket,commands}=fixture({...refusal,pageTextReady:false});
    await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',waitStagesMs:[2,4,8],waitForText:'About the job',revealSelector:'#job-description',settleMs:0,WebSocketImpl:Socket});
    assert.equal(commands.some(c=>c.method==='Target.activateTarget' || c.params.expression?.includes('.scrollIntoView(')),false);
  }
});

test('selector quotes remain data in the page expressions',async()=>{
  const selector='#job\");globalThis.injected=true;//';
  const {Socket,commands}=fixture({pageTextReady:false,textAfterReveal:true});
  await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',waitStagesMs:[2,4,8],waitForText:'About the job',revealSelector:selector,settleMs:0,WebSocketImpl:Socket});
  const selected=[],scrolled=[];
  const context={injected:false,document:{querySelector(value){selected.push(value);return {scrollIntoView(options){scrolled.push(options.block);}};}}};
  for(const c of commands.filter(c=>c.params.expression?.includes('document.querySelector('))) runInNewContext(c.params.expression,context);
  assert.deepEqual(selected,[selector,selector]);
  assert.equal(context.injected,false);
  assert.deepEqual(scrolled,['center']);
});

for (const refusal of [{status:403},{pageRefusal:true}]) {
  test('a refusal ends further rendering waits: '+JSON.stringify(refusal),async()=>{
    const {Socket}=fixture({...refusal,pageReadyState:'interactive'});
    const result=await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',waitStagesMs:[2,4,8],settleMs:0,WebSocketImpl:Socket});
    assert.deepEqual(result.render_wait_budgets_ms,[2]);
    assert.equal(result.load_timed_out,false);
  });
}

test('concurrent captures never share a session or tab',async()=>{
  const a=fixture(),b=fixture();
  await Promise.all([a,b].map(f=>capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',settleMs:0,WebSocketImpl:f.Socket})));
  for(const f of [a,b]) {
    assert.deepEqual(f.commands.filter(c=>c.method==='Target.closeTarget').map(c=>c.params.targetId),[f.target]);
    assert.ok(f.commands.filter(c=>/^(Page|Runtime|Network)\./.test(c.method)).every(c=>c.sessionId===f.session));
  }
});

test('invalid navigation is rejected before opening a socket',async()=>{
  const {Socket,commands}=fixture();
  await assert.rejects(capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'file:///etc/passwd',WebSocketImpl:Socket}),/HTTP/);
  assert.equal(commands.length,0);
});

test('only the selected daily browser endpoint is discovered',async()=>{
  const home=await mkdtemp(join(tmpdir(),'job-hunt-cdp-'));
  try {
    await mkdir(join(home,'.config/google-chrome'),{recursive:true});
    await writeFile(join(home,'.config/google-chrome/DevToolsActivePort'),'9222\n/devtools/browser/chrome\n');
    assert.equal(await dailyEndpoint('chrome',{platform:'linux',home}),'ws://127.0.0.1:9222/devtools/browser/chrome');
    await assert.rejects(dailyEndpoint('edge',{platform:'linux',home}),/Cannot find edge/);
  } finally {await rm(home,{recursive:true,force:true});}
});

test('Chrome and Edge discovery covers macOS, Windows and Linux daily profiles',async()=>{
  const home=await mkdtemp(join(tmpdir(),'job-hunt-platforms-'));
  const cases=[
    ['darwin','chrome','Library/Application Support/Google/Chrome'],
    ['darwin','edge','Library/Application Support/Microsoft Edge'],
    ['win32','chrome','Local/Google/Chrome/User Data'],
    ['win32','edge','Local/Microsoft/Edge/User Data'],
    ['linux','chrome','.config/google-chrome'],
    ['linux','edge','.config/microsoft-edge'],
  ];
  try {
    for(const [platform,browser,path] of cases){
      await mkdir(join(home,path),{recursive:true});
      await writeFile(join(home,path,'DevToolsActivePort'),`9222\n/devtools/browser/${platform}-${browser}\n`);
      assert.equal(await dailyEndpoint(browser,{platform,home,localAppData:join(home,'Local')}),`ws://127.0.0.1:9222/devtools/browser/${platform}-${browser}`);
    }
  } finally {await rm(home,{recursive:true,force:true});}
});

// Execute the actual page expression against observed DOM-like nodes, rather
// than merely asserting that a click-shaped CDP command was emitted.
function navigationDom(labels, {form=false, tag='DIV', href=null}={}) {
  const clicks=[], events=[], assignments=[];
  const nodes=labels.map(label=>({innerText:label,tagName:tag,disabled:false,
    getClientRects:()=>[{}],getAttribute:key=>key==='href'?href:null,
    contains:()=>false,closest(selector){return selector==='form'?(form?{}:null):this;},
    click(){clicks.push(label);}}));
  const context={URL,location:{href:'https://example.com/jobs',assign:url=>assignments.push(url)},
    window:{},getComputedStyle:()=>({visibility:'visible'}),
    document:{querySelectorAll:()=>nodes,addEventListener:type=>events.push(type)}};
  return {context,clicks,events,assignments,nodes};
}

test('an exact observed job label navigates without selecting a pre-existing tab',async()=>{
  const {clickExpression}=await import('../browser_cdp.mjs');
  const f=navigationDom(['（2027届校招）投资银行股权业务线助理']);
  const result=runInNewContext(clickExpression('（2027届校招）投资银行股权业务线助理'),f.context);
  assert.equal(result.performed,true);
  assert.equal(result.action,'navigate');
  assert.deepEqual(f.clicks,['（2027届校招）投资银行股权业务线助理']);
  assert.deepEqual(f.events,['submit']);
  f.context.window.open('/jobs/123');
  assert.deepEqual(f.assignments,['https://example.com/jobs/123']);
  assert.throws(()=>f.context.window.open('javascript:alert(1)'),/Invalid navigation/);
});

test('ambiguous, missing, form and application controls never click',async()=>{
  const {clickExpression}=await import('../browser_cdp.mjs');
  for(const [labels,label,options] of [
    [['详情','详情'],'详情',{}], [[], '详情',{}],
    [['立即投递'],'立即投递',{}], [['Apply now'],'Apply now',{}],
    [['下一页'],'下一页',{form:true}], [['详情'],'详情',{tag:'A',href:'javascript:submit()'}],
  ]) {
    const f=navigationDom(labels,options);
    assert.ok(runInNewContext(clickExpression(label),f.context).error);
    assert.deepEqual(f.clicks,[]);
  }
});

test('navigation labels and selectors remain data, not page code',async()=>{
  const {clickExpression}=await import('../browser_cdp.mjs');
  const label='岗位 "); globalThis.injected=true; //', selector='#node "); globalThis.injected=true; //';
  const f=navigationDom([label]);f.context.injected=false;
  assert.equal(runInNewContext(clickExpression(label,selector),f.context).performed,true);
  assert.equal(f.context.injected,false);
  assert.deepEqual(f.clicks,[label]);
});

test('a document-level refusal prevents catalog navigation',async()=>{
  const {Socket,commands}=fixture({status:403});
  const result=await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',clickText:'岗位详情',settleMs:0,WebSocketImpl:Socket});
  assert.equal(result.blocked,true);
  assert.equal(commands.some(c=>c.params.expression?.includes('node.click()')),false);
  assert.equal(commands.at(-1).method,'Target.closeTarget');
});

test('inert javascript:void(0) detail links invoke their observed click handler',async()=>{
  const {clickExpression}=await import('../browser_cdp.mjs');
  const f=navigationDom(['详情'],{tag:'A',href:'javascript:void(0)'});
  assert.equal(runInNewContext(clickExpression('详情'),f.context).performed,true);
  assert.deepEqual(f.clicks,['详情']);
  assert.equal(f.nodes[0].target,'_self');
});


test('a complete SPA login wall stops immediately when detail text is missing',async()=>{
  const {Socket,commands}=fixture({pageRefusal:true,pageTextReady:false});
  const result=await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',waitForText:'任职资格',settleMs:0,waitStagesMs:[50,100,200],WebSocketImpl:Socket});
  assert.equal(result.blocked,true);
  assert.equal(result.load_timed_out,false);
  assert.deepEqual(result.render_wait_budgets_ms,[50]);
  assert.equal(commands.filter(c=>c.params.expression==='document.readyState').length,1);
  assert.equal(commands.at(-1).method,'Target.closeTarget');
});

test('rendered text excludes scripts, hidden text and an unrendered body',async()=>{
  const {VISIBLE_TEXT_EXPRESSION, REFUSAL}=await import('../browser_cdp.mjs');
  const nodes=[
    {textContent:'投行校招', rendered:true},
    {textContent:'请输入验证码', excluded:true, rendered:true},
    {textContent:'请填写验证码', hidden:true, rendered:true},
    {textContent:'请完成验证码', rendered:false},
  ];
  for(const n of nodes) n.parentElement={closest:()=>n.excluded, node:n};
  const context={NodeFilter:{SHOW_TEXT:4},getComputedStyle:p=>({visibility:p.node.hidden?'hidden':'visible'}),
    document:{body:{},createTreeWalker:()=>{let i=0;return {nextNode:()=>nodes[i++]};},
      createRange:()=>{let node;return {selectNodeContents:n=>{node=n;},getClientRects:()=>node.rendered?[{}]:[]};}}};
  assert.equal(runInNewContext(VISIBLE_TEXT_EXPRESSION,context),'投行校招');
  nodes[2].hidden=false;
  assert.ok(REFUSAL.test(runInNewContext(VISIBLE_TEXT_EXPRESSION,context)));
  for(const n of nodes) n.rendered=false;
  assert.equal(runInNewContext(VISIBLE_TEXT_EXPRESSION,context),'');
});

test('two navigation steps use one owned tab and preserve intermediate snapshots',async()=>{
  const {Socket,commands}=fixture();
  const result=await capture({endpoint:'ws://localhost/devtools/browser/test',url:'https://example.com/',
    steps:[{text:'Location'},{text:'Mainland China',selector:'label[for="location-mainland-china"]'}],settleMs:0,WebSocketImpl:Socket});
  assert.equal(result.navigation_steps.length,2);
  assert.ok(result.navigation_steps.every(s=>s.source_text && s.result.text));
  assert.equal(commands.filter(c=>c.method==='Target.createTarget').length,1);
  assert.equal(commands.filter(c=>c.method==='Page.navigate').length,1);
  assert.equal(commands.filter(c=>c.params.expression?.includes('node.click()')).length,2);
});

test('a refusal after step one prevents step two and still closes its owned tab',async()=>{
  const {Socket,commands}=fixture({refuseAfterClick:true,pageTextReady:[true,false]});
  // The first control is ready; after its click the requested next label is absent.
  const result=await capture({endpoint:'ws://localhost/devtools/browser/test',url:'https://example.com/',
    steps:[{text:'Location'},{text:'Mainland China'}],waitStagesMs:[1],settleMs:0,WebSocketImpl:Socket});
  assert.equal(result.blocked,true);
  assert.equal(commands.filter(c=>c.params.expression?.includes('node.click()')).length,1);
  assert.equal(commands.at(-1).method,'Target.closeTarget');
});

test('navigation sequence rejects unbounded or malformed plans before connecting',async()=>{
  for(const steps of [Array(9).fill({text:'Next'}),[{}],{},[{text:'Next',selector:1}]]) {
    await assert.rejects(capture({steps}),/at most eight/);
  }
});

test('only an explicitly selected filter button may use the Apply verb',async()=>{
  const {clickExpression}=await import('../browser_cdp.mjs');
  const allowed=navigationDom(['Apply all filters'],{tag:'BUTTON'});
  assert.equal(runInNewContext(clickExpression('Apply all filters','.apply-filters'),allowed.context).performed,true);
  for(const [label,selector,options] of [
    ['Apply all filters','',{tag:'BUTTON'}],
    ['Apply all filters','.apply-filters',{tag:'BUTTON',form:true}],
    ['Apply all filters','.apply-filters',{tag:'A'}],
    ['Apply now','.apply-filters',{tag:'BUTTON'}],
  ]) {
    const f=navigationDom([label],options);
    assert.ok(runInNewContext(clickExpression(label,selector),f.context).error);
    assert.equal(f.clicks.length,0);
  }
});

test('rendered node boundaries normalize for waiting and refusal without changing raw text',async()=>{
  const {NORMAL_TEXT_EXPRESSION,REFUSAL}=await import('../browser_cdp.mjs');
  const nodes=['请输入','验证码'].map(textContent=>({textContent,parentElement:{closest:()=>null}}));
  const context={NodeFilter:{SHOW_TEXT:4},getComputedStyle:()=>({visibility:'visible'}),
    document:{body:{},createTreeWalker:()=>{let i=0;return {nextNode:()=>nodes[i++]};},
      createRange:()=>({selectNodeContents:()=>{},getClientRects:()=>[{}]})}};
  assert.equal(runInNewContext(NORMAL_TEXT_EXPRESSION,context),'请输入 验证码');
  assert.ok(REFUSAL.test(runInNewContext(NORMAL_TEXT_EXPRESSION,context)));
});

test('page number waits for a unique visible control, not a digit in the footer',async()=>{
  const {navigationReadyExpression}=await import('../browser_cdp.mjs');
  const f=navigationDom(['©2025']);
  assert.equal(runInNewContext(navigationReadyExpression('5'),f.context),false);
  f.nodes[0].innerText='5';
  assert.equal(runInNewContext(navigationReadyExpression('5'),f.context),true);
  f.nodes[0].getClientRects=()=>[];
  assert.equal(runInNewContext(navigationReadyExpression('5'),f.context),false);
  const ambiguous=navigationDom(['5','5']);
  assert.equal(runInNewContext(navigationReadyExpression('5'),ambiguous.context),false);
});

test('unaccounted navigation and over-budget journeys fail before connecting',async()=>{
  const f=fixture();
  const options={endpoint:'ws://localhost/devtools/browser/test',url:'https://example.com/',steps:[{text:'Next'}],WebSocketImpl:f.Socket};
  await assert.rejects(rawCapture(options),/NAVIGATION_BUDGET_REQUIRED/);
  const b=budgetFor(1,{used_rows:10,stages:[{row_selector:'.card',page:1,max_rows:10},{row_selector:'.card',page:2,max_rows:10}]});
  await assert.rejects(rawCapture({...options,budget:b}),/planned 30 rows/);
  assert.equal(f.commands.length,0);
  assert.throws(()=>validateBudget({...b,used_rows:0,used_pages:[3]},1),/3 pages/);
});

test('every intermediate catalog contributes once and rows are preserved',async()=>{
  const f=fixture({catalogCounts:[10,10,5]});
  const b=budgetFor(2,{stages:[1,1,2].map((page,i)=>({row_selector:'.card',page,max_rows:i===2?5:10}))});
  const result=await capture({endpoint:'ws://localhost/devtools/browser/test',url:'https://example.com/',
    steps:[{text:'Filter'},{text:'Next'}],budget:b,settleMs:0,WebSocketImpl:f.Socket});
  assert.equal(result.navigation_budget.observed_rows,25);
  assert.deepEqual(result.navigation_budget.observed_pages,[1,2]);
  assert.equal(result.navigation_steps[0].source_snapshot.catalog_rows.length,10);
  assert.equal(result.navigation_steps[0].result.catalog_rows.length,10);
  assert.equal(result.catalog_rows.length,5);
  assert.doesNotThrow(()=>JSON.stringify(result));
});

test('unexpected first-page overflow is saved and prevents every subsequent click',async()=>{
  const f=fixture({catalogCounts:[26,0]});
  const b=budgetFor(1,{stages:[{row_selector:'.card',page:1,max_rows:20},{row_selector:'.card',page:2,max_rows:5}]});
  const result=await capture({endpoint:'ws://localhost/devtools/browser/test',url:'https://example.com/',
    steps:[{text:'Next'}],budget:b,settleMs:0,WebSocketImpl:f.Socket});
  assert.equal(result.budget_exceeded,true);
  assert.equal(result.navigation_budget.observed_rows,26);
  assert.equal(f.commands.filter(c=>c.params.expression?.includes('node.click()')).length,0);
  assert.equal(f.commands.at(-1).method,'Target.closeTarget');
});

test('a later click failure retains all earlier catalogs and closes its own tab',async()=>{
  const {Socket,commands,target}=fixture({catalogCounts:[10,10],failClick:2});
  const budget=budgetFor(2,{stages:[10,10,5].map((max_rows,index)=>({row_selector:'.job',page:Math.min(index+1,2),max_rows}))});
  const result=await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',
    steps:[{text:'Next'},{text:'Job details'}],budget,settleMs:0,WebSocketImpl:Socket});
  assert.equal(result.navigation_error.message,'Control disappeared');
  assert.equal(result.navigation_steps.length,1);
  assert.equal(result.navigation_budget.observed_rows,20);
  assert.equal(result.navigation_steps[0].source_snapshot.catalog_rows.length,10);
  assert.equal(result.catalog_rows.length,10);
  assert.doesNotThrow(()=>JSON.stringify(result));
  assert.deepEqual(commands.filter(c=>c.method==='Target.closeTarget').map(c=>c.params.targetId),[target]);
});

test('an HTTP failure never advances to another catalog',async()=>{
  const {Socket,commands}=fixture({status:500,catalogCounts:[10,10]});
  const result=await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',
    clickText:'Next',budget:budgetFor(1,{stages:[10,10].map(max_rows=>({row_selector:'.job',page:1,max_rows}))}),
    settleMs:0,WebSocketImpl:Socket});
  assert.equal(result.http_status,500);
  assert.equal(result.navigation_budget.observed_rows,0);
  assert.equal(commands.filter(c=>c.params.expression?.includes('node.click()')).length,0);
});

test('unknown catalog inspection preserves the page but never claims zero rows',async()=>{
  const {Socket,commands}=fixture();
  const result=await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',
    clickText:'Campus',budget:budgetFor(1,{stages:[{row_selector:null,page:1,max_rows:0},{row_selector:null,page:1,max_rows:25}]}),
    settleMs:0,WebSocketImpl:Socket});
  assert.equal(result.catalog_accounting_pending,true);
  assert.equal(result.navigation_budget.observed_rows,null);
  assert.equal(result.navigation_budget.stages[1].row_count,null);
  assert.equal(result.navigation_steps[0].source_snapshot.catalog_rows.length,0);
  assert.equal(commands.filter(c=>c.params.expression?.includes('node.click()')).length,1);
  assert.equal(commands.at(-1).method,'Target.closeTarget');
  assert.throws(()=>validateBudget(budgetFor(2,{stages:[{row_selector:null,page:1,max_rows:25},{row_selector:'.job',page:1,max_rows:0},{row_selector:'.job',page:1,max_rows:0}]}),2),/final inspection/);
  assert.throws(()=>validateBudget(budgetFor(0,{stages:[{row_selector:null,page:1,max_rows:10}]}),0),/full unused allowance/);
  assert.doesNotThrow(()=>validateBudget(budgetFor(0,{max_rows:10,stages:[{row_selector:null,page:1,max_rows:10}]}),0));
});

test('a refused diagnostic remains a site stop, not pending catalog accounting',async()=>{
  const {Socket}=fixture({status:403});
  const result=await capture({endpoint:'ws://127.0.0.1:9222/devtools/browser/test',url:'https://example.com/',
    budget:budgetFor(0,{stages:[{row_selector:null,page:1,max_rows:25}]}),settleMs:0,WebSocketImpl:Socket});
  assert.equal(result.blocked,true);
  assert.equal(result.catalog_accounting_pending,undefined);
  assert.equal(result.navigation_budget.observed_rows,0);
});
