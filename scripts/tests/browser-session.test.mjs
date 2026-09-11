import {test} from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
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
