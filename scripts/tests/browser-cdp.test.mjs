import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, mkdir, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {capture, dailyEndpoint} from '../browser_cdp.mjs';

let fixtureId = 0;
function fixture({status=200, navigationError=false, pageReadyState='complete', pageRefusal=false, pageTextReady=true, readyAfterWait=false, textAfterWait=false}={}) {
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
