#!/usr/bin/env node
/** Standalone, read-only CDP capture. Requires Node 22+, no npm dependencies. */
import {readFile, writeFile} from 'node:fs/promises';
import {homedir} from 'node:os';
import {join, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

export async function dailyEndpoint(browser, {platform = process.platform, home = homedir(), localAppData = process.env.LOCALAPPDATA} = {}) {
  if (!['chrome', 'edge'].includes(browser)) throw Error('Select the customer daily browser: chrome or edge');
  const roots = platform === 'darwin'
    ? {chrome: join(home, 'Library/Application Support/Google/Chrome'), edge: join(home, 'Library/Application Support/Microsoft Edge')}
    : platform === 'win32'
      ? {chrome: join(localAppData || join(home, 'AppData/Local'), 'Google/Chrome/User Data'), edge: join(localAppData || join(home, 'AppData/Local'), 'Microsoft/Edge/User Data')}
      : {chrome: join(home, '.config/google-chrome'), edge: join(home, '.config/microsoft-edge')};
  let lines;
  try { lines = (await readFile(join(roots[browser], 'DevToolsActivePort'), 'utf8')).trim().split(/\r?\n/); }
  catch { throw Error(`Cannot find ${browser} remote-debugging endpoint. Enable remote debugging in the selected daily browser; no separate browser is started.`); }
  const port = Number(lines[0]);
  if (!Number.isInteger(port) || port < 1 || port > 65535 || !/^\/devtools\/browser(?:\/[^\s?#]+)?$/.test(lines[1] || '')) throw Error('Invalid daily-browser debugging endpoint');
  return `ws://127.0.0.1:${port}${lines[1]}`;
}

export async function capture({endpoint, url, settleMs = 1500, timeoutMs = 15000, WebSocketImpl = globalThis.WebSocket}) {
  const targetUrl = new URL(url);
  if (!['http:', 'https:'].includes(targetUrl.protocol) || targetUrl.username || targetUrl.password) throw Error('Capture URL must be HTTP(S), without credentials');
  const socketUrl = new URL(endpoint);
  if (!['ws:', 'wss:'].includes(socketUrl.protocol) || !socketUrl.pathname.startsWith('/devtools/browser')) throw Error('Use a browser-level CDP WebSocket endpoint');
  if (!WebSocketImpl) throw Error('Node 22+ is required for the built-in CDP reader');
  const ws = new WebSocketImpl(endpoint);
  let seq = 0, sessionId, targetId, frameId;
  const pending = new Map(), responses = [], trace = [];
  function send(method, params = {}, session = sessionId, deadline = timeoutMs) {
    return new Promise((ok, fail) => {
      const id = ++seq;
      const timer = setTimeout(() => { pending.delete(id); fail(Error(`CDP timeout: ${method}`)); }, deadline);
      pending.set(id, {ok, fail, timer});
      const command = {id, method, params};
      if (session) command.sessionId = session;
      trace.push({method, targetId: targetId || null, sessionId: session || null});
      try { ws.send(JSON.stringify(command)); } catch (err) {clearTimeout(timer);pending.delete(id);fail(err);}
    });
  }
  ws.addEventListener('message', event => {
    let msg; try { msg = JSON.parse(event.data); } catch {return;}
    const item = pending.get(msg.id);
    if (item) { clearTimeout(item.timer);pending.delete(msg.id);msg.error ? item.fail(Error(msg.error.message)) : item.ok(msg.result); }
    if (msg.sessionId === sessionId && msg.method === 'Network.responseReceived' && msg.params.type === 'Document') responses.push(msg.params);
  });
  ws.addEventListener('close', () => {
    for (const p of pending.values()) {clearTimeout(p.timer);p.fail(Error('CDP connection closed'));} pending.clear();
  });
  try {
    await new Promise((ok, fail) => {
      const timer = setTimeout(() => fail(Error('CDP connection timeout; check browser connection consent')), timeoutMs);
      ws.addEventListener('open', () => {clearTimeout(timer);ok();}, {once:true});
      ws.addEventListener('error', () => {clearTimeout(timer);fail(Error('CDP connection failed'));}, {once:true});
    });
    ({targetId} = await send('Target.createTarget', {url:'about:blank', background:true}));
    if (!targetId) throw Error('CDP did not create a task-owned tab');
    ({sessionId} = await send('Target.attachToTarget', {targetId, flatten:true}));
    if (!sessionId) throw Error('CDP did not attach the task-owned tab');
    await send('Page.enable');await send('Network.enable');
    const navigation = await send('Page.navigate', {url});
    frameId = navigation.frameId;
    if (navigation.errorText) throw Error(`Navigation failed: ${navigation.errorText}`);
    const deadline = Date.now() + timeoutMs;
    let ready = false;
    while (Date.now() < deadline) {
      const r = await send('Runtime.evaluate', {expression:'document.readyState', returnByValue:true});
      if (r.result?.value === 'complete') {ready = true;break;}
      await new Promise(r => setTimeout(r, 250));
    }
    if (!ready) throw Error('Page did not finish loading within the capture deadline');
    if (settleMs) await new Promise(r => setTimeout(r, settleMs));
    const r = await send('Runtime.evaluate', {expression:`({url:location.href,title:document.title,retrieved_at:new Date().toISOString(),text:document.body?.innerText||'',links:[...new Set([...document.querySelectorAll('a[href]')].map(a=>a.href).filter(u=>/^https?:/.test(u)))],http_status:null})`, returnByValue:true});
    if (r.exceptionDetails || !r.result?.value?.url) throw Error('Could not read the page snapshot');
    const snapshot = r.result.value;
    const response = responses.filter(x => x.frameId === frameId && x.response.url === snapshot.url).at(-1);
    snapshot.http_status = response?.response.status ?? null;
    snapshot.capture = {backend:'builtin-cdp', targetId, trace};
    return snapshot;
  } finally {
    try {
      if (targetId && ws.readyState === 1) {
        const result = await send('Target.closeTarget', {targetId}, null, 3000);
        if (!result.success) throw Error('CDP did not confirm closing the task-owned tab');
      }
    } finally {ws.close();}
  }
}

export async function main(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--help') {console.log('node scripts/browser_cdp.mjs --browser chrome|edge --url URL --output raw/site-capture.json [--endpoint ws://.../devtools/browser/...]');return;}
    if (!['--browser','--url','--output','--endpoint'].includes(argv[i]) || !argv[i+1]) throw Error(`Unknown or incomplete argument: ${argv[i]}`);
    args[argv[i].slice(2)] = argv[++i];
  }
  if (!args.url || !args.output) throw Error('--url and --output are required');
  const endpoint = args.endpoint || await dailyEndpoint(args.browser);
  const snapshot = await capture({endpoint, url:args.url});
  await writeFile(args.output, JSON.stringify(snapshot, null, 2), {flag:'wx'});
  console.log(JSON.stringify({output:args.output, url:snapshot.url, http_status:snapshot.http_status, characters:snapshot.text.length, backend:'builtin-cdp'}));
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main(process.argv.slice(2)).catch(err => {console.error(err.message);process.exitCode=1;});
}
