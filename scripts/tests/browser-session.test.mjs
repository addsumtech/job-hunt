import {test} from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {mkdtemp, readFile, writeFile, mkdir, rm, realpath} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {promisify} from 'node:util';
import {execFile} from 'node:child_process';
import {createSession} from '../browser_session.mjs';
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
    const c=client();await call(c,1,'Target.createTarget',{url:'about:blank'});c.close();await tick();
    assert.equal(connections,1);
    assert.equal(session.status().owned_tabs,0);
    upstream.close();await tick();
    assert.equal(connections,1);
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
