#!/usr/bin/env node
/** One consented Chrome connection, isolated CDP clients, no automatic reconnect. */
import {createServer} from 'node:http';
import {randomBytes} from 'node:crypto';
import {createRequire} from 'node:module';
import {readFile, writeFile, mkdir, unlink, open, rename, stat} from 'node:fs/promises';
import {join, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {spawn} from 'node:child_process';
import {dailyEndpoint} from './browser_cdp.mjs';

const alive = pid => {try {process.kill(pid, 0);return true;} catch {return false;}};
const send = (ws, value) => {if (ws?.readyState === 1) ws.send(JSON.stringify(value));};
const failed = state => ['disconnected', 'consent_timeout'].includes(state);
const active = state => ['connected', 'waiting_for_consent'].includes(state);
const connectionHelp = browser => `Cannot connect to the selected daily ${browser}. Keep it open and ${browser === 'chrome' ? 'enable remote debugging at chrome://inspect/#remote-debugging' : 'enable its supported remote-debugging endpoint'}, then start one session and accept the browser's connection prompt.`;
// WorkBuddy waits at most 600 s on a foreground Bash call (BASH_MAX_TIMEOUT_MS),
// then moves it to the background and keeps the process. A model that runs
// `start` without run_in_background is blocked until then and cannot tell the
// user to accept Chrome's prompt, so the consent window must outlast that wait.
export const consentMsFor = env => env.CODEBUDDY_SANDBOX_BROKER_EXECUTION_ATTEMPT_ID ? 11 * 60 * 1000 : 120000;
const resumeHelp = 'Do not reconnect automatically. WorkBuddy can reset it from a new chat after the user asks to resume, or the user can reset it from a terminal.';
// Say why the session ended. Every ending used to carry the remote-debugging
// instructions, so a session that had merely idled out (live on 2026-11-19) was
// reported to the user as "Chrome has remote debugging turned off".
const ENDINGS = {
  stopped: 'The browser session was stopped.',
  idle_timeout: 'The browser session expired after 30 idle minutes.',
  browser_disconnected: 'The browser closed the authorized connection (it was closed, restarted, or the connection was revoked).',
  consent_timeout: "The browser's connection prompt was not accepted in time.",
  // Never written by the session itself: a killed process records nothing. It
  // is derived from a record that still says connected/waiting while no session
  // process answers. That record has no ended_reason, so it used to fall through
  // to the remote-debugging instructions below.
  process_gone: 'The browser session process is no longer running (it was killed, it crashed, or the machine restarted).',
};
const settingsIntact = "The browser's remote-debugging setting is not the cause.";
// Endings nobody chose: the user did not stop the session and the browser did
// not refuse it. The same chat may start one new session; the browser asks the
// user for consent again, so this cannot reconnect behind their back.
const RESTARTABLE = ['idle_timeout', 'process_gone'];
const restartHelp = "Run browser-session start once in this chat and ask the user to accept the browser's connection prompt again; no reset is needed.";
const corruptHelp = file => `The browser session state file is unreadable (damaged or half-written): ${file}. ${settingsIntact} Run browser-session reset once to clear it, then start one session and accept the browser's connection prompt.`;
const stoppedHelp = (browser, reason) => {
  if (reason === 'consent_timeout') return `${ENDINGS[reason]} ${resumeHelp} Then start one session and accept the browser's connection prompt.`;
  if (RESTARTABLE.includes(reason)) return `${ENDINGS[reason]} ${settingsIntact} ${restartHelp}`;
  if (ENDINGS[reason]) return `${ENDINGS[reason]} ${settingsIntact} ${resumeHelp}`;
  // connection_refused, or a record written before reasons were kept.
  return `The browser session ended. ${resumeHelp} ${connectionHelp(browser)}`;
};
// A state change holds the lock for a few seconds at most (a start waits about
// five for its child). A lock older than this was left by a killed process.
const LOCK_STALE_MS = 30000;

export async function createSession({endpoint, WebSocket, WebSocketServer,
  idleMs = 30 * 60 * 1000, consentMs = 120000, changed = () => {}}) {
  const token = randomBytes(24).toString('hex');
  const socketPath = `/devtools/browser/${token}`;
  const pending = new Map(), owners = new Map(), sessionTargets = new Map(), targets = new Map(), clients = new Set();
  let sequence = 0, state = 'waiting_for_consent', lastUse = Date.now(), closing = false, everConnected = false, reason;
  const server = createServer((req, res) => {
    if (!req.headers.origin && req.url === socketPath + '/status' && req.method === 'GET') {
      res.setHeader('Content-Type','application/json');
      // Measured, not asserted: 1 only while the one upstream socket is open.
      res.end(JSON.stringify({pid:process.pid,state,clients:clients.size,owned_tabs:targets.size,upstream_connections:upstream.readyState === 1 ? 1 : 0}));return;
    }
    if (!req.headers.origin && req.url === socketPath + '/stop' && req.method === 'POST') {
      if (clients.size) {res.writeHead(409);res.end('Active clients still use this session');return;}
      res.end('stopping');void close('closed','stopped');return;
    }
    res.writeHead(404);res.end();
  });
  const downstream = new WebSocketServer({noServer:true, maxPayload:8 * 1024 * 1024});
  const upstream = new WebSocket(endpoint);
  const publish = () => changed({state, reason, clients:clients.size, owned_tabs:targets.size});
  function forward(client, command, cleanup = false) {
    const id = ++sequence;
    pending.set(id, {client, original:command.id, command, cleanup});
    upstream.send(JSON.stringify({...command, id}));
  }
  function closeTarget(targetId) {
    if (upstream.readyState === 1) forward(null, {method:'Target.closeTarget',params:{targetId}}, true);
  }
  function allowed(client, command) {
    const {method, params = {}, sessionId} = command;
    if (sessionId && owners.get(sessionId) !== client) return false;
    if (method === 'Target.createTarget') {
      if (sessionId || params.browserContextId) return false;
      try {
        const u = new URL(params.url);
        return (params.url === 'about:blank' || ['http:', 'https:'].includes(u.protocol)) && !u.username && !u.password;
      } catch {return false;}
    }
    if (method === 'JobHunt.handoffTarget') return !sessionId && targets.get(params.targetId) === client;
    if (['Target.attachToTarget','Target.closeTarget','Target.getTargetInfo','Target.activateTarget'].includes(method)) {
      return targets.get(params.targetId) === client;
    }
    if (method === 'Target.detachFromTarget') return owners.get(params.sessionId) === client;
    if (method.startsWith('Target.') || method.startsWith('Browser.')) return method === 'Browser.getVersion';
    return Boolean(sessionId);
  }
  server.on('upgrade', (req, socket, head) => {
    // Only a local tool holding this session's random path can connect. Web
    // pages with an Origin are not clients of this local transport.
    if (req.url !== socketPath || req.headers.origin || state !== 'connected') {
      socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n');return;
    }
    downstream.handleUpgrade(req, socket, head, ws => downstream.emit('connection', ws));
  });
  downstream.on('connection', client => {
    clients.add(client);lastUse = Date.now();publish();
    client.on('error', () => {});
    client.on('message', raw => {
      let command;
      try {command = JSON.parse(raw.toString());} catch {client.close(1007);return;}
      if (!Number.isInteger(command?.id) || typeof command.method !== 'string') {client.close(1007);return;}
      if (!allowed(client, command)) {
        send(client, {id:command.id,error:{code:-32000,message:'CDP operation is outside this client-owned tab/session'}});return;
      }
      if (command.method === 'JobHunt.handoffTarget') {
        // A login/verification page now belongs to the user. Release it before
        // acknowledging, so disconnect/idle/stop cleanup cannot close it and
        // this client cannot keep operating its formerly attached session.
        const targetId = command.params.targetId;
        targets.delete(targetId);
        for (const [id, target] of sessionTargets) if (target === targetId) {
          owners.delete(id);sessionTargets.delete(id);
          forward(null, {method:'Target.detachFromTarget',params:{sessionId:id}}, true);
        }
        lastUse = Date.now();
        forward(client, {id:command.id,method:'Target.activateTarget',params:{targetId}});
        publish();return;
      }
      lastUse = Date.now();forward(client, command);
    });
    client.on('close', () => {
      clients.delete(client);lastUse = Date.now();
      for (const [targetId, owner] of targets) if (owner === client) closeTarget(targetId);
      publish();
    });
  });
  // The idle clock starts at consent, not at launch: in WorkBuddy the prompt
  // may wait 11 minutes, and those came out of the "30 idle minutes".
  upstream.on('open', () => {state = 'connected';everConnected = true;lastUse = Date.now();clearTimeout(consentTimer);publish();});
  upstream.on('error', () => {});
  upstream.on('message', raw => {
    let message;try {message = JSON.parse(raw.toString());} catch {return;}
    const item = pending.get(message.id);
    if (item) {
      pending.delete(message.id);
      const {client, command} = item;
      if (!message.error) {
        if (command.method === 'Target.createTarget' && message.result?.targetId) {
          targets.set(message.result.targetId, client);
          // A client can disappear before its creation response arrives.
          if (!clients.has(client)) closeTarget(message.result.targetId);
        }
        if (command.method === 'Target.attachToTarget' && message.result?.sessionId) {
          if (targets.get(command.params.targetId) === client && clients.has(client)) {
            owners.set(message.result.sessionId, client);
            sessionTargets.set(message.result.sessionId, command.params.targetId);
          } else {
            // An attach can finish after handoff or client disconnect. Never
            // restore access to a page that was already released to the user.
            forward(null, {method:'Target.detachFromTarget',params:{sessionId:message.result.sessionId}}, true);
          }
        }
        if (command.method === 'Target.closeTarget' && message.result?.success) targets.delete(command.params.targetId);
        if (command.method === 'Target.detachFromTarget') {owners.delete(command.params.sessionId);sessionTargets.delete(command.params.sessionId);}
      }
      send(client, {...message,id:item.original});publish();return;
    }
    if (message.method === 'Target.detachedFromTarget') {owners.delete(message.params?.sessionId);sessionTargets.delete(message.params?.sessionId);}
    if (message.method === 'Target.targetDestroyed') targets.delete(message.params?.targetId);
    // Never broadcast another client's events or pre-existing browser tabs.
    const owner = owners.get(message.sessionId) || targets.get(message.params?.targetId);
    if (owner) send(owner, message);
  });
  const close = async (finalState = 'closed', why = 'stopped') => {
    if (closing) return;
    closing = true;state = finalState;reason = why;publish();clearTimeout(consentTimer);clearInterval(idleTimer);
    for (const targetId of targets.keys()) closeTarget(targetId);
    for (const client of clients) client.close(1001);
    if (upstream.readyState === 1) await new Promise(r => setTimeout(r, 100));
    upstream.close();downstream.close();server.close();publish();
  };
  upstream.on('close', () => {
    if (closing) return;
    clearTimeout(consentTimer);
    for (const client of clients) client.close(1011, 'Browser connection ended; wait for the user to resume');
    pending.clear();void close('disconnected', everConnected ? 'browser_disconnected' : 'connection_refused');
  });
  const consentTimer = setTimeout(() => {void close('consent_timeout','consent_timeout');}, consentMs);
  const idleTimer = setInterval(() => {if (!clients.size && Date.now() - lastUse > idleMs) void close('closed','idle_timeout');}, Math.min(idleMs, 30000));
  await new Promise((ok, fail) => {server.once('error', fail);server.listen(0, '127.0.0.1', ok);});
  return {endpoint:`ws://127.0.0.1:${server.address().port}${socketPath}`, close,
    status:() => ({state,reason,clients:clients.size,owned_tabs:targets.size})};
}

export async function main(argv) {
  const options = {};
  const action = argv.shift();
  for (let i=0;i<argv.length;i+=2) {
    if (!['--root','--browser'].includes(argv[i]) || !argv[i+1]) throw Error('Use start|status|stop|reset --root PATH --browser chrome|edge');
    options[argv[i].slice(2)] = argv[i+1];
  }
  if (!options.root || !['chrome','edge'].includes(options.browser)) throw Error('--root and --browser are required');
  const root = resolve(options.root), browser = options.browser;
  const managed = Boolean(process.env.CODEBUDDY_SANDBOX_BROKER_EXECUTION_ATTEMPT_ID);
  const workbuddySession = managed ? process.env.CODEBUDDY_SANDBOX_BROKER_SESSION_ID : undefined;
  await mkdir(root, {recursive:true});
  const stateFile = join(root, `browser-session-${browser}.json`), lockFile = stateFile + '.lock';
  // A damaged record is reported as such instead of surfacing a JSON parser
  // message from every command, `reset` included, with no way to clear it.
  async function readState() {
    let raw;
    try {raw = await readFile(stateFile,'utf8');}
    catch (err) {if (err.code === 'ENOENT') return undefined;throw err;}
    try {
      const record = JSON.parse(raw);
      if (record && typeof record === 'object' && !Array.isArray(record)) return record;
    } catch {}
    return {corrupt:true};
  }
  // A live pid is not a live session. The record outlives its process (it is
  // kept after stop), and the pid is later handed to an unrelated program: a
  // cleanly stopped record then made `start` answer "stopping; wait" and
  // `reset` answer "wait for it to stop" until that program happened to exit.
  // So ask the recorded endpoint who it is. Its path is this session's random
  // token; only that session answers there with this pid. A probe that merely
  // times out stays "live": a busy session must never be replaced by a second
  // browser connection.
  async function probe(record) {
    if (!Number.isInteger(record?.pid) || record.pid <= 0 || !alive(record.pid) || typeof record.endpoint !== 'string') return {live:false};
    try {
      const url = new URL(record.endpoint);url.protocol = 'http:';url.pathname += '/status';
      const response = await fetch(url,{signal:AbortSignal.timeout(2000)});
      if (!response.ok) return {live:false};
      const status = await response.json();
      return status?.pid === record.pid ? {live:true,status} : {live:false};
    } catch (err) {return {live:err?.name === 'TimeoutError'};}
  }
  let previous, live = false, liveStatus;
  async function load() {
    previous = await readState();
    ({live, status:liveStatus} = await probe(previous));
  }
  // The record still claims a session and no session process answers.
  const gone = () => active(previous?.state) && !live;
  const ending = () => gone() ? 'process_gone' : previous?.ended_reason;
  await load();
  async function withStartLock(action) {
    const token = randomBytes(8).toString('hex');
    const claim = () => writeFile(lockFile,JSON.stringify({pid:process.pid,at:Date.now(),token}),{flag:'wx',mode:0o600});
    try {await claim();} catch (err) {
      if (err.code !== 'EEXIST') throw err;
      // The lock used to be an empty file with no owner, so one left behind by
      // a killed command refused every later start, stop and reset. Take it
      // over when its holder is gone or it is older than any state change. An
      // unreadable or ownerless lock (an older version's) is judged by age.
      let holder = {}, age = Infinity;
      try {holder = JSON.parse(await readFile(lockFile,'utf8')) || {};} catch {}
      try {age = Date.now() - (Number.isFinite(holder.at) ? holder.at : (await stat(lockFile)).mtimeMs);} catch {}
      if (age < LOCK_STALE_MS && (!Number.isInteger(holder.pid) || alive(holder.pid))) throw Error('A browser session state change is in progress; check status');
      await unlink(lockFile).catch(() => {});
      try {await claim();} catch (again) {
        if (again.code === 'EEXIST') throw Error('A browser session state change is in progress; check status');
        throw again;
      }
    }
    try {return await action();}
    finally {
      // Release only our own lock; a slow command may have been taken over.
      try {if (JSON.parse(await readFile(lockFile,'utf8')).token === token) await unlink(lockFile);} catch {}
    }
  }
  async function contact(suffix, method = 'GET') {
    if (!previous?.endpoint || !live) throw Error('No running browser session');
    const url = new URL(previous.endpoint);url.protocol = 'http:';url.pathname += suffix;
    const response = await fetch(url,{method,signal:AbortSignal.timeout(2000)});
    if (!response.ok) throw Error(await response.text());
    return response;
  }
  const currentStatus = async () => liveStatus ?? await (await contact('/status')).json();
  if (action === 'status') {
    if (previous?.corrupt) throw Error(corruptHelp(stateFile));
    if (failed(previous?.state)) throw Error(stoppedHelp(browser, previous.ended_reason));
    if (!live || previous.state === 'closed') {
      const reason = ending();
      console.log(JSON.stringify({state:'stopped',browser,...(reason ? {reason} : {})}));return;
    }
    const status = await currentStatus();
    if (failed(status.state)) throw Error(stoppedHelp(browser, previous.ended_reason));
    console.log(JSON.stringify({...status,browser}));return;
  }
  if (action === 'endpoint') {
    if (previous?.corrupt) throw Error(corruptHelp(stateFile));
    if (failed(previous?.state)) throw Error(stoppedHelp(browser, previous.ended_reason));
    if (!live && (previous?.state === 'closed' || gone())) {
      const reason = ending();
      throw Error(`${ENDINGS[reason] || ENDINGS.stopped} ${settingsIntact} No browser session is running.${RESTARTABLE.includes(reason) ? ` ${restartHelp}` : ''}`);
    }
    const status = await currentStatus();
    if (status.state !== 'connected') throw Error(`Browser session is ${status.state}; wait for user consent instead of opening another connection`);
    if (previous.source_endpoint !== await dailyEndpoint(browser)) throw Error(stoppedHelp(browser, previous.ended_reason));
    console.log(previous.endpoint);return;
  }
  if (action === 'stop') {
    return withStartLock(async () => {
      await load();
      if (previous?.corrupt) throw Error(corruptHelp(stateFile));
      if (live) {
        if (active(previous.state)) await contact('/stop','POST');
        console.log(JSON.stringify({state:'stopping',browser}));return;
      }
      console.log(JSON.stringify({state:'stopped',browser}));
    });
  }
  if (action === 'reset') {
    return withStartLock(async () => {
      await load();
      if (live) throw Error('Wait for the existing browser session to stop before resetting');
      // A damaged record names no chat, so the new-chat rule below cannot be
      // applied to it; refusing would leave it in place for good.
      if (managed && previous && !previous.corrupt && (!workbuddySession || !previous.workbuddy_session ||
          workbuddySession === previous.workbuddy_session)) throw Error(stoppedHelp(browser, ending()));
      if (previous) await unlink(stateFile);
      console.log(JSON.stringify({state:'stopped',browser}));
    });
  }
  if (action === 'serve' && !managed) return serve();
  if (action !== 'start') throw Error('Use start, status, stop or reset');
  return withStartLock(async () => {
    await load();
    if (previous?.corrupt) throw Error(corruptHelp(stateFile));
    // Checked first: a session still shutting down is about to become one of
    // the cases below, and "stopping; wait" is the only true answer until then.
    if (live && previous.state === 'closed') throw Error('Browser session is stopping; wait for status to report stopped');
    // An idle expiry is neither a failure nor a stop the user asked for: the
    // session ran out while the chat waited (for the user's answers, on
    // 2026-11-19). Refusing the next start left that chat with no way to read a
    // single page. One new start asks for consent once; it cannot loop, because
    // each expiry needs another 30 idle minutes. A session whose process was
    // killed is the same kind of ending. Every other ending still waits for the
    // user and a new chat.
    const restartable = RESTARTABLE.includes(ending());
    if (failed(previous?.state) || (managed && previous?.state === 'closed' && !restartable)) throw Error(stoppedHelp(browser, previous.ended_reason));
    if (live) {
      if (previous.source_endpoint !== await dailyEndpoint(browser)) throw Error(stoppedHelp(browser, previous.ended_reason));
      const status = await currentStatus();
      if (failed(status.state)) throw Error(stoppedHelp(browser, previous.ended_reason));
      console.log(JSON.stringify({...status,browser,reused:true}));return;
    }
    let sourceEndpoint;
    try {sourceEndpoint = await dailyEndpoint(browser);} catch (err) {throw Error(`${err.message}. ${connectionHelp(browser)}`);}
    if (managed) {
      // WorkBuddy revokes the broker capability when its Bash task exits.
      // Keep the server in that task. WorkBuddy runs the task in background.
      const session = await serve(sourceEndpoint);
      console.log(JSON.stringify({...session.status(),browser,pid:process.pid,reused:false}));
      return;
    }
    const log = await open(join(root,`browser-session-${browser}.log`),'a',0o600);
    const child = spawn(process.execPath,[process.argv[1],'serve','--root',root,'--browser',browser],
      {detached:true,stdio:['ignore',log.fd,log.fd],windowsHide:true});
    child.unref();await log.close();
    // Hold the lock until the child publishes its state. Count the handshake
    // grace from that point so a slow process launch does not eat the grace.
    let firstState = null;
    for (let i=0;i<100;i++) {
      const state = await readState();
      if (state?.pid===child.pid) {
        if (firstState === null) firstState = i;
        if (failed(state.state)) throw Error(stoppedHelp(browser, state.ended_reason));
        if (state.state === 'closed') throw Error(connectionHelp(browser));
        if (state.state !== 'waiting_for_consent' || i - firstState >= 20) {
          console.log(JSON.stringify({state:state.state,browser,pid:state.pid,reused:false}));return;
        }
      }
      await new Promise(r=>setTimeout(r,50));
    }
    throw Error('Browser session did not start; inspect its local log');
  });

  async function serve(sourceEndpoint) {
    const runtime = JSON.parse(await readFile(join(root,'runtime.json'),'utf8'));
    const {WebSocket,WebSocketServer} = createRequire(runtime.opencli)('ws');
    const source_endpoint = sourceEndpoint ?? await dailyEndpoint(browser);
    const stagingFile = `${stateFile}.${process.pid}.tmp`;
    let localEndpoint, lastState, writes = Promise.resolve();
    const save = ({state, reason}) => {
      if (!localEndpoint || lastState === state) return;
      lastState = state;
      writes = writes.then(async () => {
        await writeFile(stagingFile,JSON.stringify({pid:process.pid,browser,
          source_endpoint,endpoint:localEndpoint,state,...(reason ? {ended_reason:reason} : {}),workbuddy_session:workbuddySession}),{mode:0o600});
        await rename(stagingFile,stateFile);
      });
    };
    const session = await createSession({endpoint:source_endpoint,WebSocket,WebSocketServer,changed:save,
      consentMs:consentMsFor(process.env)});
    localEndpoint = session.endpoint;
    save(session.status());
    process.once('SIGTERM',()=>{void session.close();});
    process.once('SIGINT',()=>{void session.close();});
    await writes;
    return session;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main(process.argv.slice(2)).catch(err=>{console.error(err.message);process.exitCode=1;});
}
