import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, mkdir, readFile, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {runInNewContext} from 'node:vm';

async function loadBridge(root) {
  const files = {
    'package.json':'{"type":"module"}',
    'node_modules/ws/package.json':'{"type":"module","main":"index.js"}',
    'node_modules/ws/index.js':`import {EventEmitter} from 'node:events';
      export class WebSocket extends EventEmitter {static OPEN=1;
        constructor(){super();this.readyState=1;queueMicrotask(()=>this.emit('open'));}
        close(){this.readyState=3;}
      }`,
    'browser/utils.js':'export const buildEvaluateExpression=x=>x;',
    'browser/stealth.js':'export const generateStealthJs=()=>"";',
    'browser/dom-helpers.js':'export const waitForDomStableJs="";',
    'browser/base-page.js':'export class CDPBasePage {}',
    'utils.js':'export const isRecord=x=>x && typeof x==="object"; export const saveBase64ToFile=()=>{};',
    'electron-apps.js':'export const getAllElectronApps=()=>[];',
  };
  for(const [name,body] of Object.entries(files)) {
    const file=join(root,name);
    await mkdir(join(file,'..'),{recursive:true});
    await writeFile(file,body);
  }
  await writeFile(join(root,'browser/cdp.js'),await readFile(new URL('../../assets/opencli-cdp/cdp.js',import.meta.url)));
  return import(pathToFileURL(join(root,'browser/cdp.js')).href);
}

test('OpenCLI hands a verification page to the user and only cleans completed task tabs',async()=>{
  const root=await mkdtemp(join(tmpdir(),'opencli-handoff-'));
  try {
    const {CDPBridge}=await loadBridge(root);
    for(const [wall,direct] of [[false,false],[true,false],[true,true]]) {
      const bridge=new CDPBridge(), calls=[];
      let closed=0;
      bridge._targetId='created-by-this-client';
      bridge._sessionId='owned-session';
      bridge._ws={readyState:1,close:()=>closed++};
      bridge.send=async(method,params)=>{
        calls.push({method,params});
        if(method==='Runtime.evaluate') return {result:{value:wall}};
        if(method==='JobHunt.handoffTarget' && direct) throw Error("'JobHunt.handoffTarget' wasn't found");
        return {success:true};
      };
      await bridge.close();
      assert.equal(closed,1);
      const cleanups=calls.filter(c=>c.method==='Target.closeTarget');
      assert.equal(cleanups.length,wall?0:1);
      if(wall) {
        assert.equal(calls.find(c=>c.method==='JobHunt.handoffTarget').params.targetId,'created-by-this-client');
        if(direct) {
          assert.equal(calls.find(c=>c.method==='Target.activateTarget').params.targetId,'created-by-this-client');
          assert.equal(calls.find(c=>c.method==='Target.detachFromTarget').params.sessionId,'owned-session');
        }
      } else assert.equal(cleanups[0].params.targetId,'created-by-this-client');
      assert.ok(!calls.some(c=>c.method==='Browser.close'||c.method==='Target.getTargets'));
    }
  } finally {await rm(root,{recursive:true,force:true});}
});

test('OpenCLI connects an owned tab without changing browser fingerprints',async()=>{
  const root=await mkdtemp(join(tmpdir(),'opencli-connect-'));
  try {
    const {CDPBridge}=await loadBridge(root);
    const bridge=new CDPBridge(),calls=[];
    bridge.send=async(method,params)=>{
      calls.push({method,params});
      if(method==='Target.createTarget')return {targetId:'owned'};
      if(method==='Target.attachToTarget')return {sessionId:'session'};
      return {};
    };
    await bridge.connect({cdpEndpoint:'ws://127.0.0.1/devtools/browser/fixture'});
    assert.deepEqual(calls.map(c=>c.method),['Target.createTarget','Target.attachToTarget','Page.enable']);
    assert.equal(calls[0].params.background,true);
    await bridge.close();
  } finally {await rm(root,{recursive:true,force:true});}
});

test('handoff detection uses visible wall text, not login links or hidden source',async()=>{
  const root=await mkdtemp(join(tmpdir(),'opencli-wall-'));
  try {
    const {USER_ACTION_EXPRESSION}=await loadBridge(root);
    function page(text,{hidden=false,rendered=true,hostname='example.test',pathname='/jobs'}={}) {
      const node={textContent:text};
      node.parentElement={closest:()=>false};
      return {NodeFilter:{SHOW_TEXT:4},location:{hostname,pathname},
        getComputedStyle:()=>({visibility:hidden?'hidden':'visible',display:'block'}),
        document:{body:{},createTreeWalker:()=>{let read=false;return {nextNode:()=>read?null:(read=true,node)};},
          createRange:()=>({selectNodeContents:()=>{},getClientRects:()=>rendered?[{}]:[]})}};
    }
    for(const text of ['请完成验证码','请按住滑块，拖动到最右边','Please\nsign\nin to continue','验证成功。正在等待网站响应']) {
      assert.equal(runInNewContext(USER_ACTION_EXPRESSION,page(text)),true,text);
      assert.equal(runInNewContext(USER_ACTION_EXPRESSION,page(text,{hidden:true})),false);
      assert.equal(runInNewContext(USER_ACTION_EXPRESSION,page(text,{rendered:false})),false);
    }
    assert.equal(runInNewContext(USER_ACTION_EXPRESSION,page('Product Manager · Login · Careers')),false);
    assert.equal(runInNewContext(USER_ACTION_EXPRESSION,page('',{hostname:'www.zhipin.com',pathname:'/web/passport/zp/security.html'})),true);
    assert.equal(runInNewContext(USER_ACTION_EXPRESSION,page('',{hostname:'www.zhipinXcom',pathname:'/web/passport/zp/security.html'})),false);
  } finally {await rm(root,{recursive:true,force:true});}
});
