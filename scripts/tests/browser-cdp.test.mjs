import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, mkdir, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {runInNewContext} from 'node:vm';
import {capture, dailyEndpoint} from '../browser_cdp.mjs';

let fixtureId = 0;
function fixture({status=200, navigationError=false, pageReadyState='complete', pageRefusal=false, pageTextReady=true, readyAfterWait=false, textAfterWait=false, revealNodeExists=true, textAfterReveal=false}={}) {
  const commands=[];
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
        if(c.method==='Runtime.evaluate') result={result:{value:c.params.expression==='document.readyState'?(Array.isArray(pageReadyState)?pageReadyState.shift() || 'complete':pageReadyState):c.params.expression.startsWith('Boolean(document.body')?(Array.isArray(pageTextReady)?pageTextReady.shift():pageTextReady):c.params.expression.startsWith('Boolean(')?pageRefusal:{url:'https://example.com/',title:'Fixture',text:'Visible job description',links:[]}}};
        if(c.method==='Runtime.evaluate' && c.params.expression.startsWith('Boolean(\n')) {
          if(readyAfterWait) pageReadyState='complete';
          if(textAfterWait) pageTextReady=true;
        }
        if(c.method==='Runtime.evaluate' && c.params.expression.startsWith('Boolean(document.querySelector')) result={result:{value:revealNodeExists}};
        if(c.method==='Runtime.evaluate' && c.params.expression.includes('.scrollIntoView(')) {
          result={result:{value:revealNodeExists}};
          if(textAfterReveal) pageTextReady=true;
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
function navigationDom(labels, {form=false, tag='DIV', href=null, role=null, value=null}={}) {
  const clicks=[], events=[], assignments=[];
  const nodes=labels.map(label=>({innerText:label,value,tagName:tag,disabled:false,
    getClientRects:()=>[{}],getAttribute:key=>key==='href'?href:key==='role'?role:null,
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

// 2026-09-19 review: BOSS's 立即沟通 messages the recruiter (irreversible), and
// the skill serves nl/de/fr markets whose apply/login words the list lacked.
const ACTION_LABELS=['立即沟通','继续沟通','聊一聊','感兴趣','关注','关注公司','收藏职位','举报','分享',
  '立即申请','申请职位','一键投递','Follow','Connect','Message','I\'m interested','Easy Apply','Save job',
  'Solliciteer nu','Solliciteren','Inloggen','Aanmelden','Jetzt bewerben','Anmelden','Postuler','Se connecter',
  'Sign up','Log on',
  // adversarial pass: verb plus object/modifier, and state toggles
  '申请该职位','在线申请','收藏该职位','应聘该职位','取消收藏','已收藏','立即报名','一键申请','免费注册',
  'Save this job','Unsave','Follow company','Message recruiter','Report this job','Share this job',
  'Vacature opslaan','Job speichern','Bewerben Sie sich','Apply on company site','Jetzt bewerben ›','立即沟通 >','感兴趣 ♡',
  // independent reviewer's list (not tuned by the author of the matcher)
  '投个简历','关注他','关注TA','联系HR','打招呼','I’m interested','Following','Merken','Reageer direct',
  'Envoyer ma candidature','Je postule','エントリーする','気になる','즉시지원','입사지원','Create job alert',
  'Chat with recruiter','立即 沟通','Ａｐｐｌｙ','登录/注册','登录后查看','提交申请','Log in to apply','Sign in with Google','Register now',
  '申请加入','私信','发消息','立即咨询','Send message','Bericht sturen','Contacteer ons','Nachricht senden','Kontakt aufnehmen','Envoyer un message','Save for later','I am interested',
  '이력서 등록하기','会員登録する','Bewaar deze vacature','Jobalarm erstellen','Add to my jobs','Upload your CV',
  // 2026-09-20 review: 88 labels harvested from real boards; these 56 were not refused.
  '投简历','发简历','简历投递','职位申请','附件简历投递','同意并投递','登录后投递','扫码登录','微信登录','验证码登录',
  '手机号登录','上传简历','完善简历','电话联系','微信联系','预约面试','预约宣讲会','报名参加',
  'Start Your Application','Use My Last Application','Autofill with Resume','Create Account','Join now',
  'Continue with Google','Post your resume','Upload your resume','Attach resume','Withdraw application',
  'Add a Salary','Write a review','Add to favorites','Add to my jobs','Bewaar vacature','Maak jobalert',
  'Jobalarm erstellen','Konto erstellen','Créer une alerte emploi','Contacter le recruteur',
  'キープする','保存する','会員登録','メッセージを送る','스크랩','회원가입','메시지 보내기','이력서 등록'];
const JOB_TITLES=['Design Intern','Registered Nurse','注册会计师（审计）','Catalog Integration Engineer',
  '专利申请代理人','Chat Support Agent','Report Writer','Connected Vehicle Engineer','（2027届校招）投资银行股权业务线助理',
  'CDL-A Truck Driver – $5,000 Sign-On Bonus','Single Sign-On (SSO) Engineer','Recruiting Specialist Bewerbermanagement (m/w/d)',
  'Medewerker Sollicitatiebeheer','一键部署平台研发','艺术品收藏顾问','注册会计师','Submittals Coordinator','Subscriber Growth Analyst',
  'Contact Center Agent','Share Plan Administrator','Follow-up Coordinator','Merkenbeheerder',
  'Purchase Manager','Senior Purchase Engineer','邮政投递员','订阅业务运营经理','统一登录平台开发工程师','Register Clerk',
  'Registration Coordinator','Login Security Engineer','Save the Children – Program Officer','Message Queue Engineer',
  '提交测试工程师','举报受理专员','Sign Language Interpreter','Logistics Planner','Blog Editor','Catalog Specialist',
  'Werkstudent Bewerbungsmanagement','Sachbearbeiter Bewerbermanagement','Applied Scientist',
  'Customer Contact Specialist','Message Broker Developer','发消息推送后端开发','私信风控策略','咨询顾问','Kontaktmanager Vertrieb',
  'Report Analyst (Power BI)','Checkout Engineer (Payments)','Registered Dietitian','申请人服务专员',
  // 2026-09-20 review: real titles the anywhere-lists wrongly refused. A verb that
  // also lives inside a title may only match as a whole control label.
  '数据删除合规专员','Job Alerts Product Manager','応募者管理担当','ログイン基盤エンジニア',
  '입사지원서 검토 담당자','로그인 보안 엔지니어'];

test('application, contact and account controls never click in any served language',async()=>{
  const {clickExpression}=await import('../browser_cdp.mjs');
  for(const label of ACTION_LABELS){
    const f=navigationDom([label]);
    const result=runInNewContext(clickExpression(label),f.context);
    assert.ok(result.error,`clicked ${label}`);
    assert.deepEqual(f.clicks,[],label);
  }
});

test('job titles that merely contain an action word still navigate',async()=>{
  const {clickExpression}=await import('../browser_cdp.mjs');
  for(const label of JOB_TITLES){
    const f=navigationDom([label]);
    assert.equal(runInNewContext(clickExpression(label),f.context).performed,true,label);
    assert.deepEqual(f.clicks,[label]);
  }
});

// Structural rule. A catalog job title is a link; application, contact and
// account controls are buttons. No word list can keep up with every board, so a
// button-like control is refused unless it reads as pagination or a detail link.
test('a button-like control is refused even when no word list names it',async()=>{
  const {clickExpression}=await import('../browser_cdp.mjs');
  const cases=[
    ['立即投递',{tag:'BUTTON'}], ['Create Account',{tag:'BUTTON'}],
    ['一键直达',{tag:'BUTTON'}],        // in no word list: refused by shape alone
    ['Quick action',{tag:'BUTTON'}],
    ['Weiter zum Profil',{tag:'BUTTON'}],
    ['Create Account',{tag:'DIV',role:'button'}],
    ['立即投递',{tag:'DIV',role:'button'}],
    ['Senior Platform Engineer',{tag:'BUTTON'}], // a title on a button is still a button
    ['提交',{tag:'INPUT',value:'提交'}],
  ];
  for(const [label,options] of cases){
    const f=navigationDom([label],options);
    const result=runInNewContext(clickExpression(label),f.context);
    assert.ok(result.error,`clicked ${label} (${JSON.stringify(options)})`);
    assert.deepEqual(f.clicks,[],label);
  }
});

test('pagination and detail controls still navigate, as buttons or as links',async()=>{
  const {clickExpression}=await import('../browser_cdp.mjs');
  const cases=[
    ['下一页',{tag:'BUTTON'}], ['上一页',{tag:'BUTTON'}], ['Next',{tag:'BUTTON'}],
    ['Previous',{tag:'BUTTON'}], ['»',{tag:'BUTTON'}], ['‹',{tag:'BUTTON'}],
    ['2',{tag:'BUTTON'}], ['第 3 页',{tag:'BUTTON'}], ['Next page',{tag:'BUTTON'}],
    ['查看详情',{tag:'BUTTON'}], ['职位详情',{tag:'BUTTON'}], ['查看更多',{tag:'BUTTON'}],
    ['展开',{tag:'BUTTON'}], ['收起',{tag:'BUTTON'}], ['View details',{tag:'BUTTON'}],
    ['Show more',{tag:'BUTTON'}], ['Meer tonen',{tag:'BUTTON'}], ['Mehr anzeigen',{tag:'BUTTON'}],
    ['Voir plus',{tag:'BUTTON'}], ['もっと見る',{tag:'BUTTON'}], ['더보기',{tag:'BUTTON'}],
    ['Volgende',{tag:'BUTTON'}], ['Nächste Seite',{tag:'BUTTON'}], ['Suivant',{tag:'BUTTON'}],
    ['次へ',{tag:'BUTTON'}], ['다음',{tag:'BUTTON'}],
    ['下一页',{tag:'DIV',role:'button'}],
    ['Senior Platform Engineer',{tag:'A',href:'/jobs/42'}],
    ['（2027届校招）投资银行股权业务线助理',{tag:'A',href:'/jobs/7'}],
    ['数据删除合规专员',{tag:'A',href:'/jobs/8'}],
  ];
  for(const [label,options] of cases){
    const f=navigationDom([label],options);
    const result=runInNewContext(clickExpression(label),f.context);
    assert.equal(result.performed,true,`refused ${label} (${JSON.stringify(options)})`);
    assert.deepEqual(f.clicks,[label],label);
  }
});

test('the page expression and isActionControl share one vocabulary',async()=>{
  const {clickExpression,isActionControl,isSafeNavigationLabel}=await import('../browser_cdp.mjs');
  // The structural allowance is the same predicate the page expression inlines.
  for(const label of ['下一页','»','2','查看详情','View details','더보기','Senior Platform Engineer','Create Account','一键极速投递']){
    const f=navigationDom([label],{tag:'BUTTON'});
    const navigated=runInNewContext(clickExpression(label),f.context).performed===true;
    assert.equal(navigated,isSafeNavigationLabel(label) && !isActionControl(label),`button branch disagrees on ${label}`);
  }
  for(const label of ACTION_LABELS) assert.equal(isActionControl(label),true,`isActionControl missed ${label}`);
  for(const label of JOB_TITLES) assert.equal(isActionControl(label),false,`isActionControl refused title ${label}`);
  // Same decision when reached through the page expression, on a plain link.
  for(const label of [...ACTION_LABELS,...JOB_TITLES]){
    const f=navigationDom([label],{tag:'A',href:'/x'});
    const refused=Boolean(runInNewContext(clickExpression(label),f.context).error);
    assert.equal(refused,isActionControl(label),`page expression and isActionControl disagree on ${label}`);
  }
});
