import {test} from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter, once} from 'node:events';
import {mkdtemp, readFile, writeFile, mkdir, rm, realpath, utimes, access} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {promisify} from 'node:util';
import {execFile, spawn} from 'node:child_process';
import {createSession, consentMsFor} from '../browser_session.mjs';
const tick = () => new Promise(r=>setImmediate(r));

test('successive clients share one connection and cannot access each others tabs', async()=>{
  let connections=0, upstream, downstream, target=0;
  const commands=[];
  class Socket extends EventEmitter {
    constructor(){super();connections++;upstream=this;this.readyState=1;queueMicrotask(()=>this.emit('open'));}
    send(raw){const c=JSON.parse(raw);commands.push(c);queueMicrotask(()=>{
      let result={};
      if(c.method==='Target.createTarget')result={targetId:`t${++target}`};
      if(c.method==='Target.attachToTarget')result={sessionId:`s-${c.params.targetId}`};
      if(c.method==='Target.closeTarget')result={success:true};
      this.emit('message',JSON.stringify({id:c.id,result}));
    });}
    close(){this.readyState=3;this.emit('close');}
  }
  class Server extends EventEmitter {constructor(){super();downstream=this;}close(){}}
  const session=await createSession({endpoint:'ws://fixture',WebSocket:Socket,WebSocketServer:Server});
  function client(){const c=new EventEmitter();c.readyState=1;c.received=[];c.send=raw=>c.received.push(JSON.parse(raw));c.close=()=>{c.readyState=3;c.emit('close');};downstream.emit('connection',c);return c;}
  async function call(c,id,method,params={},sessionId){c.emit('message',JSON.stringify({id,method,params,sessionId}));await tick();return c.received.at(-1);}
  try {
    const a=client(), b=client();
    const ta=(await call(a,1,'Target.createTarget',{url:'about:blank'})).result.targetId;
    const tb=(await call(b,1,'Target.createTarget',{url:'about:blank'})).result.targetId;
    assert.notEqual(ta,tb);
    assert.ok((await call(b,2,'Target.attachToTarget',{targetId:ta})).error);
    assert.ok((await call(a,2,'Target.getTargets')).error);
    const sa=(await call(a,3,'Target.attachToTarget',{targetId:ta,flatten:true})).result.sessionId;
    assert.ok((await call(b,3,'Runtime.evaluate',{expression:'1'},sa)).error);
    upstream.emit('message',JSON.stringify({sessionId:sa,method:'Page.loadEventFired'}));
    assert.equal(a.received.at(-1).method,'Page.loadEventFired');
    assert.notEqual(b.received.at(-1).method,'Page.loadEventFired');
    a.close();await tick();
    assert.ok(commands.some(c=>c.method==='Target.closeTarget'&&c.params.targetId===ta));
    assert.ok(!commands.some(c=>c.method==='Target.closeTarget'&&c.params.targetId===tb));
    b.close();await tick();
    const c=client();
    const tc=(await call(c,1,'Target.createTarget',{url:'https://example.test/verify'})).result.targetId;
    const sc=(await call(c,2,'Target.attachToTarget',{targetId:tc,flatten:true})).result.sessionId;
    assert.ok((await call(c,3,'JobHunt.handoffTarget',{targetId:'existing-user-tab'})).error);
    assert.ok(!(await call(c,4,'JobHunt.handoffTarget',{targetId:tc})).error);
    assert.ok(commands.some(x=>x.method==='Target.activateTarget'&&x.params.targetId===tc));
    assert.ok(commands.some(x=>x.method==='Target.detachFromTarget'&&x.params.sessionId===sc));
    assert.ok((await call(c,5,'Runtime.evaluate',{expression:'1'},sc)).error);
    assert.ok((await call(c,6,'Target.closeTarget',{targetId:tc})).error);
    c.close();await tick();
    assert.equal(connections,1);
    assert.equal(session.status().owned_tabs,0);
    await session.close();
    assert.ok(!commands.some(x=>x.method==='Target.closeTarget'&&x.params.targetId===tc));
    assert.ok(!commands.some(x=>x.method==='Target.closeTarget'&&x.params.targetId==='existing-user-tab'));
    upstream.close();await tick();
    assert.equal(connections,1);
  } finally {await session.close();}
});

test('a late attach response cannot regain access after user handoff', async()=>{
  let upstream, downstream, attach;
  const commands=[];
  class Socket extends EventEmitter {
    constructor(){super();upstream=this;this.readyState=1;queueMicrotask(()=>this.emit('open'));}
    send(raw){const c=JSON.parse(raw);commands.push(c);
      if(c.method==='Target.attachToTarget'){attach=c;return;}
      queueMicrotask(()=>this.emit('message',JSON.stringify({id:c.id,result:
        c.method==='Target.createTarget'?{targetId:'owned'}:{success:true}})));
    }
    close(){this.readyState=3;this.emit('close');}
  }
  class Server extends EventEmitter {constructor(){super();downstream=this;}close(){}}
  const session=await createSession({endpoint:'ws://fixture',WebSocket:Socket,WebSocketServer:Server});
  const client=new EventEmitter();client.readyState=1;client.received=[];
  client.send=raw=>client.received.push(JSON.parse(raw));
  client.close=()=>{client.readyState=3;client.emit('close');};
  downstream.emit('connection',client);
  const call=(id,method,params={},sessionId)=>client.emit('message',JSON.stringify({id,method,params,sessionId}));
  try {
    call(1,'Target.createTarget',{url:'about:blank'});await tick();
    call(2,'Target.attachToTarget',{targetId:'owned',flatten:true});
    call(3,'JobHunt.handoffTarget',{targetId:'owned'});await tick();
    upstream.emit('message',JSON.stringify({id:attach.id,result:{sessionId:'late-session'}}));await tick();
    call(4,'Runtime.evaluate',{expression:'document.body.innerText'},'late-session');await tick();
    assert.ok(client.received.find(r=>r.id===4).error);
    assert.ok(commands.some(c=>c.method==='Target.detachFromTarget'&&c.params.sessionId==='late-session'));
    client.close();await session.close();
    assert.ok(!commands.some(c=>c.method==='Target.closeTarget'));
  } finally {await session.close();}
});

test('connection refusal and consent timeout remain visible after cleanup', async()=>{
  for (const reason of ['disconnected','consent_timeout']) {
    let socket;
    class Socket extends EventEmitter {
      constructor(){super();socket=this;this.readyState=0;}
      close(){this.readyState=3;this.emit('close');}
    }
    class Server extends EventEmitter {close(){}}
    const states=[];
    const session=await createSession({endpoint:'ws://fixture',WebSocket:Socket,WebSocketServer:Server,
      consentMs:reason==='consent_timeout'?10:1000,changed:s=>states.push(s.state)});
    try {
      if (reason==='disconnected') {socket.emit('error',new Error('ECONNREFUSED'));socket.emit('close');}
      else await new Promise(r=>setTimeout(r,30));
      assert.equal(session.status().state,reason);
      assert.equal(states.at(-1),reason);
      await session.close();
      assert.equal(session.status().state,reason);
    } finally {await session.close();}
  }
});

test('first-run CLI gives an actionable error for missing and stale endpoints', async()=>{
  const root=await realpath(await mkdtemp(join(tmpdir(),'browser-first-run-')));
  const run=async action=>{
    try {return {code:0,...await promisify(execFile)(process.execPath,[join(root,'browser_session.mjs'),action,'--root',root,'--browser','chrome'],{timeout:10000})};}
    catch(error){return {code:error.code,stdout:error.stdout,stderr:error.stderr};}
  };
  try {
    await writeFile(join(root,'browser_session.mjs'),await readFile(new URL('../browser_session.mjs',import.meta.url)));
    await writeFile(join(root,'browser_cdp.mjs'),"export async function dailyEndpoint(){throw Error('Missing endpoint');}");
    let result=await run('start');
    assert.equal(result.code,1);
    assert.match(result.stderr,/chrome:\/\/inspect\/#remote-debugging/);
    assert.match(result.stderr,/accept the browser's connection prompt/);
    await assert.rejects(readFile(join(root,'browser-session-chrome.json')), {code:'ENOENT'});

    await writeFile(join(root,'browser_cdp.mjs'),"export async function dailyEndpoint(){return 'ws://127.0.0.1:1/devtools/browser/stale';}");
    await mkdir(join(root,'node_modules/ws'),{recursive:true});
    await writeFile(join(root,'runtime.json'),JSON.stringify({opencli:join(root,'opencli.js')}));
    await writeFile(join(root,'node_modules/ws/index.js'),`
const {EventEmitter}=require('node:events');
exports.WebSocket=class extends EventEmitter {
 constructor(){super();this.readyState=0;setImmediate(()=>{this.emit('error',Error('ECONNREFUSED'));this.emit('close');});}
 close(){this.readyState=3;this.emit('close');}
};
exports.WebSocketServer=class extends EventEmitter {close(){}};
`);
    result=await run('start');
    if(result.code===0) assert.equal(JSON.parse(result.stdout).state,'waiting_for_consent');
    else {assert.equal(result.code,1);assert.match(result.stderr,/chrome:\/\/inspect\/#remote-debugging/);}
    // A pending start can race the socket failure; the next status must retain
    // the error even after the child exits, rather than report a clean stop.
    await new Promise(r=>setTimeout(r,100));
    for (const action of ['status','endpoint']) {
      result=await run(action);
      assert.equal(result.code,1);
      assert.match(result.stderr,/chrome:\/\/inspect\/#remote-debugging/);
    }
  } finally {await rm(root,{recursive:true,force:true});}
});

test('CLI startup reports connected after an already authorized handshake', async()=>{
  const root=await realpath(await mkdtemp(join(tmpdir(),'browser-authorized-')));
  const run=action=>promisify(execFile)(process.execPath,[join(root,'browser_session.mjs'),action,'--root',root,'--browser','chrome'],{timeout:10000});
  try {
    await writeFile(join(root,'browser_session.mjs'),await readFile(new URL('../browser_session.mjs',import.meta.url)));
    await writeFile(join(root,'browser_cdp.mjs'),"export async function dailyEndpoint(){return 'ws://127.0.0.1:1/devtools/browser/authorized';}");
    await mkdir(join(root,'node_modules/ws'),{recursive:true});
    await writeFile(join(root,'runtime.json'),JSON.stringify({opencli:join(root,'opencli.js')}));
    await writeFile(join(root,'node_modules/ws/index.js'),`
const {EventEmitter}=require('node:events');
exports.WebSocket=class extends EventEmitter {
 constructor(){super();this.readyState=0;setTimeout(()=>{this.readyState=1;this.emit('open');},120);}
 close(){this.readyState=3;this.emit('close');}
};
exports.WebSocketServer=class extends EventEmitter {close(){}};
`);
    assert.equal(JSON.parse((await run('start')).stdout).state,'connected');
    assert.equal(JSON.parse((await run('status')).stdout).upstream_connections,1);
  } finally {
    try {await run('stop');} catch {}
    await new Promise(r=>setTimeout(r,100));
    await rm(root,{recursive:true,force:true});
  }
});

test('a slow start does not spend the handshake grace before the socket opens', async()=>{
  // The consent grace was `i < 20` on a counter that starts at loop entry, so
  // the wait for `serve` to write its first state ate the window meant for the
  // handshake. On a loaded machine an ALREADY AUTHORIZED browser then reports
  // waiting_for_consent and the user is sent to accept a prompt that will never
  // appear. Here `require('ws')` blocks for a second, which spends the old
  // budget deterministically instead of waiting for CI to be unlucky.
  const root=await realpath(await mkdtemp(join(tmpdir(),'browser-slow-start-')));
  const run=action=>promisify(execFile)(process.execPath,[join(root,'browser_session.mjs'),action,'--root',root,'--browser','chrome'],{timeout:20000});
  try {
    await writeFile(join(root,'browser_session.mjs'),await readFile(new URL('../browser_session.mjs',import.meta.url)));
    await writeFile(join(root,'browser_cdp.mjs'),"export async function dailyEndpoint(){return 'ws://127.0.0.1:1/devtools/browser/authorized';}");
    await mkdir(join(root,'node_modules/ws'),{recursive:true});
    await writeFile(join(root,'runtime.json'),JSON.stringify({opencli:join(root,'opencli.js')}));
    await writeFile(join(root,'node_modules/ws/index.js'),`
Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,1000);
const {EventEmitter}=require('node:events');
exports.WebSocket=class extends EventEmitter {
 constructor(){super();this.readyState=0;setTimeout(()=>{this.readyState=1;this.emit('open');},120);}
 close(){this.readyState=3;this.emit('close');}
};
exports.WebSocketServer=class extends EventEmitter {close(){}};
`);
    assert.equal(JSON.parse((await run('start')).stdout).state,'connected');
  } finally {
    try {await run('stop');} catch {}
    await new Promise(r=>setTimeout(r,100));
    await rm(root,{recursive:true,force:true});
  }
});

test('WorkBuddy keeps the session in its Bash process; a killed one restarts in the same chat, a stopped one does not', async()=>{
  const root=await realpath(await mkdtemp(join(tmpdir(),'browser-workbuddy-')));
  const args=action=>[join(root,'browser_session.mjs'),action,'--root',root,'--browser','chrome'];
  const env={...process.env,CODEBUDDY_SANDBOX_BROKER_EXECUTION_ATTEMPT_ID:'fixture',
    CODEBUDDY_SANDBOX_BROKER_SESSION_ID:'first-chat'};
  const run=(action, session=env.CODEBUDDY_SANDBOX_BROKER_SESSION_ID)=>
    promisify(execFile)(process.execPath,args(action),{
      env:{...env,CODEBUDDY_SANDBOX_BROKER_SESSION_ID:session},timeout:3000
    });
  let child;
  try {
    await writeFile(join(root,'browser_session.mjs'),await readFile(new URL('../browser_session.mjs',import.meta.url)));
    await writeFile(join(root,'browser_cdp.mjs'),"export async function dailyEndpoint(){return 'ws://127.0.0.1:1/devtools/browser/fixture';}");
    await mkdir(join(root,'node_modules/ws'),{recursive:true});
    await writeFile(join(root,'runtime.json'),JSON.stringify({opencli:join(root,'opencli.js')}));
    await writeFile(join(root,'node_modules/ws/index.js'),`
const {EventEmitter}=require('node:events');
const {appendFileSync}=require('node:fs');
const {join}=require('node:path');
exports.WebSocket=class extends EventEmitter {
 constructor(){super();appendFileSync(join(__dirname,'../../connections'),'1');this.readyState=1;queueMicrotask(()=>this.emit('open'));}
 close(){this.readyState=3;this.emit('close');}
};
exports.WebSocketServer=class extends EventEmitter {close(){}};
`);
    child=spawn(process.execPath,args('start'),{env,stdio:['ignore','pipe','inherit']});
    const [line]=await once(child.stdout,'data',{signal:AbortSignal.timeout(3000)});
    assert.equal(JSON.parse(line).pid,child.pid);
    const repeated=JSON.parse((await run('start')).stdout);
    assert.equal(repeated.pid,child.pid);
    assert.equal(repeated.reused,true);
    assert.equal(JSON.parse((await run('status')).stdout).upstream_connections,1);
    assert.equal(await readFile(join(root,'connections'),'utf8'),'1');

    const exited=once(child,'exit');
    child.kill('SIGKILL');
    await exited;
    // A killed process writes no ending. Its record still said `connected`, so
    // every command answered with the remote-debugging instructions and the
    // user was sent to enable a setting that was on. Nobody chose this ending:
    // the same chat may start once more, and the browser asks for consent again.
    assert.deepEqual(JSON.parse((await run('status')).stdout),{state:'stopped',browser:'chrome',reason:'process_gone'});
    for (const [action,says] of [['endpoint',/no longer running[^]*No browser session is running/],['reset',/no longer running/]]) {
      await assert.rejects(run(action),error=>{
        assert.match(error.stderr,says);
        assert.match(error.stderr,/start once in this chat/);
        assert.doesNotMatch(error.stderr,/chrome:\/\/inspect|enable remote debugging|Do not reconnect automatically/);
        return true;
      });
    }
    // Nothing reconnected on its own while those commands ran.
    assert.equal(await readFile(join(root,'connections'),'utf8'),'1');
    child=spawn(process.execPath,args('start'),{env,stdio:['ignore','pipe','inherit']});
    const [again]=await once(child.stdout,'data',{signal:AbortSignal.timeout(3000)});
    assert.deepEqual([JSON.parse(again).pid,JSON.parse(again).reused],[child.pid,false]);
    assert.equal(await readFile(join(root,'connections'),'utf8'),'11');

    // A stop the user asked for is still final for this chat.
    const stopped=once(child,'exit');
    await run('stop');
    await stopped;
    await assert.rejects(run('start'),{stderr:/Do not reconnect automatically/});
    await assert.rejects(run('reset'),{stderr:/Do not reconnect automatically/});
    await run('reset','next-chat');
    assert.equal(JSON.parse((await run('status')).stdout).state,'stopped');
    assert.equal(await readFile(join(root,'connections'),'utf8'),'11');
  } finally {
    if (child && child.exitCode === null && child.signalCode === null) {
      const exited=once(child,'exit');
      child.kill('SIGKILL');
      await exited;
    }
    await rm(root,{recursive:true,force:true});
  }
});

test('in WorkBuddy, consent outlasts the longest foreground Bash wait', ()=>{
  // A model that forgets run_in_background is blocked for up to 600 s, after which
  // WorkBuddy backgrounds the call. The session must still be waiting when it returns.
  assert.ok(consentMsFor({CODEBUDDY_SANDBOX_BROKER_EXECUTION_ATTEMPT_ID:'x'}) > 600000);
  assert.equal(consentMsFor({}), 120000);
});

test('every ending records why, and an idle expiry is not reported as a stop', async()=>{
  const seen=[];
  class Socket extends EventEmitter {
    constructor(){super();this.readyState=1;queueMicrotask(()=>this.emit('open'));}
    send(){} close(){this.readyState=3;this.emit('close');}
  }
  class Server extends EventEmitter {close(){}}
  const idle=await createSession({endpoint:'ws://fixture',WebSocket:Socket,WebSocketServer:Server,idleMs:5,changed:x=>seen.push({...x})});
  await new Promise(r=>setTimeout(r,60));
  assert.deepEqual([idle.status().state,idle.status().reason],['closed','idle_timeout']);
  assert.ok(seen.some(x=>x.state==='closed' && x.reason==='idle_timeout'));

  let upstream;
  class Dropped extends Socket {constructor(){super();upstream=this;}}
  const dropped=await createSession({endpoint:'ws://fixture',WebSocket:Dropped,WebSocketServer:Server});
  await tick();
  upstream.close();
  assert.deepEqual([dropped.status().state,dropped.status().reason],['disconnected','browser_disconnected']);

  class Refused extends EventEmitter {
    constructor(){super();this.readyState=0;setImmediate(()=>{this.readyState=3;this.emit('close');});}
    send(){} close(){}
  }
  const refused=await createSession({endpoint:'ws://fixture',WebSocket:Refused,WebSocketServer:Server});
  await new Promise(r=>setTimeout(r,20));
  assert.deepEqual([refused.status().state,refused.status().reason],['disconnected','connection_refused']);

  class Pending extends EventEmitter {constructor(){super();this.readyState=0;} send(){} close(){this.readyState=3;}}
  const unanswered=await createSession({endpoint:'ws://fixture',WebSocket:Pending,WebSocketServer:Server,consentMs:5});
  await new Promise(r=>setTimeout(r,40));
  assert.deepEqual([unanswered.status().state,unanswered.status().reason],['consent_timeout','consent_timeout']);
});

test('WorkBuddy restarts in the same chat after an idle expiry, and only names remote debugging when it could be the cause', async()=>{
  // Live on 2026-11-19: the session was started, the chat then waited for the
  // user's search conditions, and 30 idle minutes later the session closed
  // itself. `start` refused, and its message ended with the remote-debugging
  // instructions, so the user was told to enable a setting that was already on.
  const root=await realpath(await mkdtemp(join(tmpdir(),'browser-idle-')));
  const args=action=>[join(root,'browser_session.mjs'),action,'--root',root,'--browser','chrome'];
  const env={...process.env,CODEBUDDY_SANDBOX_BROKER_EXECUTION_ATTEMPT_ID:'fixture',CODEBUDDY_SANDBOX_BROKER_SESSION_ID:'same-chat'};
  const run=action=>promisify(execFile)(process.execPath,args(action),{env,timeout:3000});
  const stateFile=join(root,'browser-session-chrome.json');
  const ended=(state,ended_reason)=>writeFile(stateFile,JSON.stringify({pid:2147483646,browser:'chrome',
    source_endpoint:'ws://127.0.0.1:1/devtools/browser/fixture',endpoint:'ws://127.0.0.1:2/devtools/browser/x',
    state,...(ended_reason ? {ended_reason} : {}),workbuddy_session:'same-chat'}));
  let child;
  try {
    await writeFile(join(root,'browser_session.mjs'),await readFile(new URL('../browser_session.mjs',import.meta.url)));
    await writeFile(join(root,'browser_cdp.mjs'),"export async function dailyEndpoint(){return 'ws://127.0.0.1:1/devtools/browser/fixture';}");
    await mkdir(join(root,'node_modules/ws'),{recursive:true});
    await writeFile(join(root,'runtime.json'),JSON.stringify({opencli:join(root,'opencli.js')}));
    await writeFile(join(root,'node_modules/ws/index.js'),`
const {EventEmitter}=require('node:events');
exports.WebSocket=class extends EventEmitter {
 constructor(){super();this.readyState=1;queueMicrotask(()=>this.emit('open'));}
 close(){this.readyState=3;this.emit('close');}
};
exports.WebSocketServer=class extends EventEmitter {close(){}};
`);
    for (const [state,reason,says] of [['closed','stopped',/was stopped/],['disconnected','browser_disconnected',/closed the authorized connection/]]) {
      await ended(state,reason);
      await assert.rejects(run('start'),error=>{
        assert.match(error.stderr,says);
        assert.match(error.stderr,/Do not reconnect automatically/);
        assert.doesNotMatch(error.stderr,/chrome:\/\/inspect|enable remote debugging/);
        return true;
      });
    }
    await ended('consent_timeout','consent_timeout');
    await assert.rejects(run('start'),{stderr:/not accepted in time[^]*accept the browser's connection prompt/});
    for (const [state,reason] of [['disconnected','connection_refused'],['disconnected',undefined]]) {
      await ended(state,reason);
      await assert.rejects(run('start'),{stderr:/chrome:\/\/inspect\/#remote-debugging/});
    }
    // A record from before reasons were kept is still a stop.
    await ended('closed');
    await assert.rejects(run('start'),{stderr:/Do not reconnect automatically/});

    await ended('closed','idle_timeout');
    assert.deepEqual(JSON.parse((await run('status')).stdout),{state:'stopped',browser:'chrome',reason:'idle_timeout'});
    await assert.rejects(run('endpoint'),{stderr:/expired after 30 idle minutes/});
    child=spawn(process.execPath,args('start'),{env,stdio:['ignore','pipe','inherit']});
    const [line]=await once(child.stdout,'data',{signal:AbortSignal.timeout(3000)});
    assert.deepEqual([JSON.parse(line).pid,JSON.parse(line).reused],[child.pid,false]);
    assert.equal(JSON.parse((await run('status')).stdout).state,'connected');
    const stopped=once(child,'exit');
    await run('stop');
    await stopped;
    assert.equal(JSON.parse(await readFile(stateFile,'utf8')).ended_reason,'stopped');
    await assert.rejects(run('start'),{stderr:/was stopped/});
  } finally {
    if (child && child.exitCode === null && child.signalCode === null) {const exited=once(child,'exit');child.kill('SIGKILL');await exited;}
    await rm(root,{recursive:true,force:true});
  }
});

// A session CLI in a private root: the script itself, a stubbed endpoint lookup
// (never the real browser) and a `ws` double that connects at once.
async function cliRoot(prefix, env={}) {
  const root=await realpath(await mkdtemp(join(tmpdir(),prefix)));
  await writeFile(join(root,'browser_session.mjs'),await readFile(new URL('../browser_session.mjs',import.meta.url)));
  await writeFile(join(root,'browser_cdp.mjs'),"export async function dailyEndpoint(){return 'ws://127.0.0.1:1/devtools/browser/fixture';}");
  await mkdir(join(root,'node_modules/ws'),{recursive:true});
  await writeFile(join(root,'runtime.json'),JSON.stringify({opencli:join(root,'opencli.js')}));
  await writeFile(join(root,'node_modules/ws/index.js'),`
const {EventEmitter}=require('node:events');
exports.WebSocket=class extends EventEmitter {
 constructor(){super();this.readyState=1;queueMicrotask(()=>this.emit('open'));}
 close(){this.readyState=3;this.emit('close');}
};
exports.WebSocketServer=class extends EventEmitter {close(){}};
`);
  const clean={...process.env};
  delete clean.CODEBUDDY_SANDBOX_BROKER_EXECUTION_ATTEMPT_ID;delete clean.CODEBUDDY_SANDBOX_BROKER_SESSION_ID;
  const args=action=>[join(root,'browser_session.mjs'),action,'--root',root,'--browser','chrome'];
  const run=(action,extra={})=>promisify(execFile)(process.execPath,args(action),{env:{...clean,...env,...extra},timeout:10000});
  const stateFile=join(root,'browser-session-chrome.json');
  const record=fields=>writeFile(stateFile,JSON.stringify({pid:2147483646,browser:'chrome',
    source_endpoint:'ws://127.0.0.1:1/devtools/browser/fixture',endpoint:'ws://127.0.0.1:1/devtools/browser/x',...fields}));
  return {root,run,args,stateFile,record,lockFile:stateFile+'.lock',env:{...clean,...env}};
}

test('a record whose pid now belongs to another program is not a live session', async()=>{
  // The record is kept after a stop and its pid is reused. `kill(pid, 0)` then
  // said "alive": status reported stopped while start said "stopping; wait" and
  // reset said "wait for it to stop", until the unrelated program exited.
  const {root,run,record}=await cliRoot('browser-pid-reuse-');
  const other=spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{stdio:'ignore'});
  try {
    await once(other,'spawn');
    await record({pid:other.pid,state:'closed',ended_reason:'stopped'});
    assert.equal(JSON.parse((await run('status')).stdout).state,'stopped');
    assert.equal(JSON.parse((await run('reset')).stdout).state,'stopped');

    // A record that still claims a connection is a lost session, not a
    // transport error ("fetch failed") on every command.
    await record({pid:other.pid,state:'connected'});
    assert.deepEqual(JSON.parse((await run('status')).stdout),{state:'stopped',browser:'chrome',reason:'process_gone'});

    // In WorkBuddy the idle restart must not be vetoed by that program either.
    const wb={CODEBUDDY_SANDBOX_BROKER_EXECUTION_ATTEMPT_ID:'fixture',CODEBUDDY_SANDBOX_BROKER_SESSION_ID:'same-chat'};
    await record({pid:other.pid,state:'closed',ended_reason:'idle_timeout',workbuddy_session:'same-chat'});
    const served=spawn(process.execPath,[join(root,'browser_session.mjs'),'start','--root',root,'--browser','chrome'],
      {env:{...process.env,...wb},stdio:['ignore','pipe','inherit']});
    try {
      const [line]=await once(served.stdout,'data',{signal:AbortSignal.timeout(5000)});
      assert.deepEqual([JSON.parse(line).pid,JSON.parse(line).reused],[served.pid,false]);
    } finally {const exited=once(served,'exit');served.kill('SIGKILL');await exited;}
  } finally {
    const exited=once(other,'exit');other.kill('SIGKILL');await exited;
    await rm(root,{recursive:true,force:true});
  }
});

test('a session still shutting down says so in WorkBuddy, even after an idle expiry', async()=>{
  // For the ~100 ms a closing session is still up, WorkBuddy's start answered
  // "Do not reconnect automatically" for an idle expiry it would accept a
  // moment later. The server here stands in for that closing session.
  const {createServer}=await import('node:http');
  const wb={CODEBUDDY_SANDBOX_BROKER_EXECUTION_ATTEMPT_ID:'fixture',CODEBUDDY_SANDBOX_BROKER_SESSION_ID:'same-chat'};
  const {root,run,record}=await cliRoot('browser-closing-',wb);
  const closing=createServer((req,res)=>res.end(JSON.stringify({pid:process.pid,state:'closed'})));
  await new Promise(ok=>closing.listen(0,'127.0.0.1',ok));
  try {
    await record({pid:process.pid,state:'closed',ended_reason:'idle_timeout',workbuddy_session:'same-chat',
      endpoint:`ws://127.0.0.1:${closing.address().port}/devtools/browser/x`});
    await assert.rejects(run('start'),error=>{
      assert.match(error.stderr,/stopping; wait/);
      assert.doesNotMatch(error.stderr,/Do not reconnect automatically/);
      return true;
    });
  } finally {closing.close();await rm(root,{recursive:true,force:true});}
});

test('a lock left by a killed command is taken over, and a held one is respected', async()=>{
  // The lock was an empty file with no owner. One left behind refused start,
  // stop and reset for good while status reported a clean stop.
  const {root,run,lockFile}=await cliRoot('browser-lock-');
  const gone=()=>assert.rejects(access(lockFile),{code:'ENOENT'});
  const old=new Date(Date.now()-120000);
  try {
    await writeFile(lockFile,JSON.stringify({pid:2147483646,at:Date.now(),token:'dead'}));
    assert.equal(JSON.parse((await run('reset')).stdout).state,'stopped');
    await gone();
    // An ownerless lock from an older version is judged by its age.
    await writeFile(lockFile,'');await utimes(lockFile,old,old);
    assert.equal(JSON.parse((await run('stop')).stdout).state,'stopped');
    await gone();
    // A live holder that has held it longer than any state change takes.
    await writeFile(lockFile,JSON.stringify({pid:process.pid,at:Date.now()-120000,token:'slow'}));
    assert.equal(JSON.parse((await run('reset')).stdout).state,'stopped');
    await gone();

    for (const held of [JSON.stringify({pid:process.pid,at:Date.now(),token:'held'}),'']) {
      await writeFile(lockFile,held);
      await assert.rejects(run('reset'),{stderr:/state change is in progress/});
      // The refused command must not release a lock it does not own.
      assert.equal(await readFile(lockFile,'utf8'),held);
    }
  } finally {await rm(root,{recursive:true,force:true});}
});

test('a damaged state file is named as such and reset clears it, in WorkBuddy too', async()=>{
  // Every command, reset included, used to fail with the JSON parser's message
  // ("Unterminated string in JSON at position 25") and leave the file in place.
  const wb={CODEBUDDY_SANDBOX_BROKER_EXECUTION_ATTEMPT_ID:'fixture',CODEBUDDY_SANDBOX_BROKER_SESSION_ID:'same-chat'};
  for (const env of [{},wb]) for (const damage of ['{"pid":123,"browser":"chr','','[]','null']) {
    const {root,run,stateFile}=await cliRoot('browser-damaged-',env);
    try {
      await writeFile(stateFile,damage);
      for (const action of ['status','endpoint','start','stop']) {
        await assert.rejects(run(action),error=>{
          assert.match(error.stderr,/state file is unreadable[^]*browser-session reset once/,action);
          assert.doesNotMatch(error.stderr,/JSON|chrome:\/\/inspect/,action);
          return true;
        });
      }
      assert.equal(await readFile(stateFile,'utf8'),damage);
      assert.equal(JSON.parse((await run('reset')).stdout).state,'stopped');
      await assert.rejects(access(stateFile),{code:'ENOENT'});
      assert.deepEqual(JSON.parse((await run('status')).stdout),{state:'stopped',browser:'chrome'});
    } finally {await rm(root,{recursive:true,force:true});}
  }
});

test('the idle clock starts when the browser accepts, not when the session was launched', async t=>{
  // Consent can take 11 minutes in WorkBuddy. Counted from launch, a session
  // accepted at minute 10 expired 20 minutes later as "30 idle minutes".
  t.mock.timers.enable({apis:['setInterval','setTimeout','Date']});
  class Socket extends EventEmitter {
    constructor(){super();this.readyState=0;setTimeout(()=>{this.readyState=1;this.emit('open');},45000);}
    send(){} close(){this.readyState=3;this.emit('close');}
  }
  class Server extends EventEmitter {close(){}}
  const session=await createSession({endpoint:'ws://fixture',WebSocket:Socket,WebSocketServer:Server,idleMs:60000,consentMs:100000});
  try {
    t.mock.timers.tick(45000);
    assert.equal(session.status().state,'connected');
    // 90 s after launch, 45 s after consent: within the limit.
    t.mock.timers.tick(45000);
    assert.equal(session.status().state,'connected');
    t.mock.timers.tick(30000);
    assert.deepEqual([session.status().state,session.status().reason],['closed','idle_timeout']);
  } finally {
    // close() waits on a mocked timer before it releases the HTTP server; let
    // it finish, or a failed assertion above would leave the test run hanging.
    void session.close();
    for (let i=0;i<3;i++) {t.mock.timers.tick(1000);await tick();}
  }
});

test('an idle expiry tells the same chat to start, on reset as on a read', async()=>{
  // reset answered "Do not reconnect automatically ... from a new chat" for the
  // one ending the guidance says to restart in place.
  const wb={CODEBUDDY_SANDBOX_BROKER_EXECUTION_ATTEMPT_ID:'fixture',CODEBUDDY_SANDBOX_BROKER_SESSION_ID:'same-chat'};
  const {root,run,record}=await cliRoot('browser-idle-reset-',wb);
  try {
    await record({state:'closed',ended_reason:'idle_timeout',workbuddy_session:'same-chat'});
    for (const action of ['reset','endpoint']) {
      await assert.rejects(run(action),error=>{
        assert.match(error.stderr,/expired after 30 idle minutes[^]*start once in this chat/,action);
        assert.doesNotMatch(error.stderr,/Do not reconnect automatically|chrome:\/\/inspect/,action);
        return true;
      });
    }
  } finally {await rm(root,{recursive:true,force:true});}
});
