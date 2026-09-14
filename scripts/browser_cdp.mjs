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

// Navigation-only helpers: data arguments are never interpolated as page code.
export const REFUSAL = /(?:verify|verifying|confirm) (?:that )?you are (?:a )?human|checking your browser|access denied|too many requests|please (?:sign|log) in|请先登[录入]|访问受限|人机验证|真人验证|请按住滑块|请完成.{0,12}验证码/i;
export const SNAPSHOT_EXPRESSION = `({url:location.href,title:document.title,retrieved_at:new Date().toISOString(),text:document.body?.innerText||'',links:[...new Set([...document.querySelectorAll('a[href]')].map(a=>a.href).filter(u=>/^https?:/.test(u)))],http_status:null})`;
export function clickExpression(text, selector = '') {
  return `(() => {
    const label = ${JSON.stringify(text)}, selector = ${JSON.stringify(selector)};
    const norm = value => (value || '').replace(/\\s+/g, ' ').trim();
    const visible = node => Boolean(node.getClientRects().length) && getComputedStyle(node).visibility !== 'hidden';
    const forbidden = /申请|应聘|投递|提交|登录|注册|收藏|订阅|删除|保存|发送|确认支付|apply|submit|sign[ -]?in|log[ -]?in|register|save|delete|subscribe|send|purchase/i;
    if (forbidden.test(label)) return {error:'Only read-only job/detail/pagination navigation is allowed'};
    let nodes;
    try {nodes = [...document.querySelectorAll(selector || 'body *')].filter(n => visible(n) && norm(n.innerText) === norm(label));}
    catch {return {error:'Invalid click selector'};}
    nodes = nodes.filter(n => !nodes.some(other => n !== other && n.contains(other)));
    if (nodes.length !== 1) return {error:'Navigation label must identify exactly one visible element; use an observed selector'};
    const node = nodes[0], control = node.closest('a,button,input,[role="button"]') || node;
    if (control.disabled || control.getAttribute('aria-disabled') === 'true' || control.closest('form') || forbidden.test(norm(control.innerText))) return {error:'Refusing a form, disabled, or account/application control'};
    const href = control.getAttribute('href');
    const inert = /^javascript:\\s*void\\s*\\(\\s*0\\s*\\)\\s*;?$/i.test(href || '');
    if (href && !inert && !/^(?:https?:|#|\\/|\\.|[^:]+$)/i.test(href)) return {error:'Refusing a non-navigation link'};
    // Keep popup-style job links inside the one task-owned tab. No submission
    // default action is allowed; explicit controls were checked above.
    document.addEventListener('submit', event => {event.preventDefault();event.stopImmediatePropagation();}, true);
    window.open = next => {const target = new URL(next, location.href);if (!['http:', 'https:'].includes(target.protocol) || target.username || target.password) throw Error('Invalid navigation URL');location.assign(target.href);return window;};
    if (control.tagName === 'A') control.target = '_self';
    node.click();
    return {performed:true,label,selector,action:'navigate',clicked_at:new Date().toISOString()};
  })()`;
}

export async function capture({endpoint, url, settleMs = 1500, timeoutMs = 15000, waitStagesMs = [timeoutMs, timeoutMs * 2, timeoutMs * 4], waitForText = '', revealSelector = '', clickText = '', clickSelector = '', inspectText = '', WebSocketImpl = globalThis.WebSocket}) {
  if (clickSelector && !clickText) throw Error('--click-selector requires --click-text');
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
    let ready = false, refused = false;
    const renderWaits = [];
    const reveal = revealSelector ? {selector:revealSelector, performed:false} : null;
    const waitForPage = async (expectedText) => {
      ready = false;refused = false;
      for (const waitMs of waitStagesMs) {
        renderWaits.push(waitMs);
        const deadline = Date.now() + waitMs;
        while (Date.now() < deadline) {
          refused = responses.some(x => x.frameId === frameId && [401, 403, 429].includes(x.response.status));
          if (refused) break;
          const r = await send('Runtime.evaluate', {expression:'document.readyState', returnByValue:true});
          if (r.result?.value === 'complete') {
            const content = expectedText ? await send('Runtime.evaluate', {
              expression:`Boolean(document.body?.innerText?.includes(${JSON.stringify(expectedText)}))`, returnByValue:true,
            }) : null;
            if (!expectedText || content.result?.value === true) {ready = true;break;}
            // A complete SPA can have redirected to login while the requested
            // detail heading remains absent. Do not wait through all three stages.
            const wallNow = await send('Runtime.evaluate', {
              expression:`Boolean(${REFUSAL.toString()}.test(document.body?.innerText || ''))`, returnByValue:true,
          });
          if (wallNow.result?.value === true) {refused = true;break;}
          }
          await new Promise(r => setTimeout(r, Math.max(1, Math.min(250, deadline - Date.now()))));
        }
        if (ready || refused) break;
        // Inspect a stalled page before waiting longer; never wait through a
        // known human-verification wall merely because its load event is pending.
        const wall = await send('Runtime.evaluate', {expression:`Boolean(
          (/(^|\\.)zhipin\\.com$/.test(location.hostname) && location.pathname === '/web/passport/zp/security.html') ||
          /请按住滑块[，,\\s]*拖动到最右边|为了更好的访问体验[，,\\s]*请进行验证|需要进行其他验证|(?:验证|确认)(?:您|你)(?:是否)?是(?:真人|人类)|(?:正在|请|需要).{0,8}(?:真人验证|人机验证)|验证成功[。.!！\\s]*正在等待|(?:您|你)所在的(?:用户组|用戶組)\\s*[（(]\\s*(?:游客|遊客)\\s*[)）]\\s*(?:无法|無法|不能)(?:进行|進行)此操作|(?:verify|verifying|confirm) (that )?you are (a )?human|checking your browser|unusual traffic/i.test(document.body?.innerText || '')
        )`, returnByValue:true});
        refused = wall.result?.value === true;
        if (refused) break;
        // Only reveal an observed lazy-loaded node after the first background
        // wait. Activation is restricted to the tab this capture created.
        if (reveal && renderWaits.length === 1) {
          const selector = JSON.stringify(revealSelector);
          const found = await send('Runtime.evaluate', {
            expression:`Boolean(document.querySelector(${selector}))`, returnByValue:true,
          });
          if (found.exceptionDetails) throw Error('Invalid reveal selector');
          if (found.result?.value !== true) throw Error(`Reveal selector not found: ${revealSelector}`);
          await send('Target.activateTarget', {targetId}, null);
          if (settleMs) await new Promise(r => setTimeout(r, settleMs));
          const scrolled = await send('Runtime.evaluate', {
            expression:`(() => {const node = document.querySelector(${selector}); if (!node) return false; node.scrollIntoView({block:'center',behavior:'instant'}); return true;})()`, returnByValue:true,
          });
          if (scrolled.exceptionDetails || scrolled.result?.value !== true) throw Error('Could not reveal the requested page node');
          reveal.performed = true;
          reveal.after_wait_stage = renderWaits.length;
          reveal.revealed_at = new Date().toISOString();
        }
      }
    };
    await waitForPage(clickText || waitForText);
    let navigationAction = null;
    if (clickText && !refused) {
      // Check the actual page even when readyState completed before the first
      // retry. A ready login/captcha page is not permission to interact.
      const before = await send('Runtime.evaluate', {expression:SNAPSHOT_EXPRESSION, returnByValue:true});
      const source = before.result?.value;
      if (!source) throw Error('Could not inspect page before navigation');
      if (REFUSAL.test(source.text)) refused = true;
      else {
        const clicked = await send('Runtime.evaluate', {expression:clickExpression(clickText, clickSelector), returnByValue:true});
        if (clicked.exceptionDetails || !clicked.result?.value?.performed) throw Error(clicked.result?.value?.error || 'Could not activate the requested navigation');
        navigationAction = {...clicked.result.value, source_url:source.url, source_text:source.text, source_links:source.links};
        if (settleMs) await new Promise(r => setTimeout(r, settleMs));
        await waitForPage(waitForText);
      }
    }
    // Ads and other resources can keep a readable page from reaching complete.
    // Preserve the actual DOM and refusal status at the deadline for diagnosis.
    if (settleMs) await new Promise(r => setTimeout(r, settleMs));
    const r = await send('Runtime.evaluate', {expression:SNAPSHOT_EXPRESSION, returnByValue:true});
    if (r.exceptionDetails || !r.result?.value?.url) throw Error('Could not read the page snapshot');
    const snapshot = r.result.value;
    if (inspectText) {
      const inspected = await send('Runtime.evaluate', {expression:`(() => {
        const label = ${JSON.stringify(inspectText)};
        const found = [...document.querySelectorAll('body *')].filter(n => n.getClientRects().length && n.innerText?.trim() === label);
        return found.filter(n => !found.some(other => n !== other && n.contains(other))).slice(0,5).map(n => ({text:n.innerText, parent_html:n.parentElement.outerHTML.slice(0,12000), truncated:n.parentElement.outerHTML.length>12000}));
      })()`, returnByValue:true});
      if (inspected.exceptionDetails) throw Error('Could not inspect the requested navigation label');
      snapshot.inspected_nodes = inspected.result?.value || [];
    }
    if (navigationAction) snapshot.navigation = navigationAction;
    if (refused) snapshot.blocked = true;
    snapshot.load_timed_out = !ready && !refused;
    snapshot.render_wait_budgets_ms = renderWaits;
    if (waitForText) snapshot.wait_for_text = waitForText;
    if (reveal) snapshot.reveal = reveal;
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
    if (argv[i] === '--help') {console.log('node scripts/browser_cdp.mjs --browser chrome|edge --url URL --output raw/site-capture.json [--wait-for-text "Expected description heading"] [--reveal-selector "Observed lazy-loaded node selector"] [--click-text "Exact observed job title or navigation label"] [--click-selector "Observed selector for an ambiguous label"] [--inspect-text "Observed label to inspect"] [--endpoint ws://.../devtools/browser/...]');return;}
    if (!['--browser','--url','--output','--endpoint','--wait-for-text','--reveal-selector','--click-text','--click-selector','--inspect-text'].includes(argv[i]) || !argv[i+1]) throw Error(`Unknown or incomplete argument: ${argv[i]}`);
    args[argv[i].slice(2)] = argv[++i];
  }
  if (!args.url || !args.output) throw Error('--url and --output are required');
  const endpoint = args.endpoint || await dailyEndpoint(args.browser);
  const snapshot = await capture({endpoint, url:args.url, waitForText:args['wait-for-text'] || '', revealSelector:args['reveal-selector'] || '', clickText:args['click-text'] || '', clickSelector:args['click-selector'] || '', inspectText:args['inspect-text'] || ''});
  await writeFile(args.output, JSON.stringify(snapshot, null, 2), {flag:'wx'});
  console.log(JSON.stringify({output:args.output, url:snapshot.url, http_status:snapshot.http_status, characters:snapshot.text.length, backend:'builtin-cdp'}));
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main(process.argv.slice(2)).catch(err => {console.error(err.message);process.exitCode=1;});
}
