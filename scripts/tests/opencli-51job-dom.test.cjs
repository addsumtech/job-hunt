// Offline integration test against the actually patched local adapter.
// NODE_PATH=<jsdom>/node_modules OPENCLI_TEST_ADAPTER_DIR=<temporary clis>
// node --test scripts/tests/opencli-51job-dom.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');
const adapters = process.env.OPENCLI_TEST_ADAPTER_DIR;
assert.ok(adapters, 'Set OPENCLI_TEST_ADAPTER_DIR to the patched adapter directory');

class CliError extends Error {
    constructor(code, message) { super(message); this.code = code; }
}

async function detail(html, detachedInnerText = 'plain') {
    const source = fs.readFileSync(path.join(adapters, '51job/detail.js'), 'utf8');
    let adapter;
    new Function('cli', 'Strategy', 'CliError', 'JOBS_ORIGIN', 'requirePage', 'navigateTo',
        source.replace(/^import .*;\s*$/gm, ''))(
        value => { adapter = value; }, { COOKIE: 'cookie' }, CliError,
        'https://jobs.51job.com', () => {}, async () => {});
    const dom = new JSDOM(html, {
        url: 'https://jobs.51job.com/shanghai/123456789.html', runScripts: 'outside-only',
    });
    Object.defineProperty(dom.window.HTMLElement.prototype, 'innerText', {
        // Chrome may return nonempty textContent-like innerText for detached
        // clones, losing <br> breaks. Also cover an empty detached innerText.
        get() { return !this.isConnected && detachedInnerText === 'empty' ? '' : this.textContent; },
    });
    let reads = 0;
    let waits = 0;
    try {
        const rows = await adapter.func({
            evaluate: async script => { reads++; return dom.window.eval(script); },
            wait: async () => { waits++; },
        }, { jobId: '123456789', url: dom.window.location.href });
        return { rows, reads, waits };
    } catch (error) {
        return { error, reads, waits };
    } finally {
        dom.window.close();
    }
}

// Exact control sentences observed in the 2026-09-12 live slider trace.
for (const prompt of ['请按住滑块，拖动到最右边', '为了更好的访问体验，请进行验证', '安全验证']) {
    test('verification control stops after one read: ' + prompt, async () => {
        const result = await detail('<h1>' + prompt + '</h1>');
        assert.equal(result.error?.code, 'ANTI_BOT');
        assert.match(result.error.message, /stop and ask the user/);
        assert.equal(result.reads, 1);
        assert.equal(result.waits, 0);
    });
}

test('ordinary validation work inside a posting is not a verification control', async () => {
    const result = await detail('<div class="cn"><h1>测试工程师</h1></div><div class="job_msg">验证产品功能，改善访问体验，测试拖动操作。</div>');
    assert.equal(result.error, undefined);
    assert.equal(result.rows[0].title, '测试工程师');
    assert.equal(result.rows[0].description, '验证产品功能，改善访问体验，测试拖动操作。');
    assert.equal(result.reads, 1);
});

test('removed posting stays distinct from a human verification page', async () => {
    const result = await detail('<h1>职位已下线</h1>');
    assert.equal(result.error?.code, 'NO_DATA');
    assert.match(result.error.message, /offline or removed/);
    assert.equal(result.reads, 1);
    assert.equal(result.waits, 0);
});

// Anonymized text in the exact header/company/address structure captured from
// 51job on 2026-09-12. The real header has no .type_4 (degree) element.
const currentCompany = `<div class="com_tag">
    <p title="示例科技有限公司" class="at p-l-0">示例科技有限公司</p>
    <p title="已上市" class="at"><span class="i_flag"></span>已上市</p>
    <p title="10000人以上" class="at"><span class="i_people"></span>10000人以上</p>
    <p title="在线生活服务(O2O)" class="at"><span class="i_trade"></span><a class="disabled">在线生活服务(O2O)</a></p>
</div>`;
const currentJob = `<div class="cn"><div class="jTitle"><h1>AI产品经理</h1><strong>3.5-4.5万</strong></div>
    <p class="msg ltype"><span class="type_2">北京</span><span class="type_3">3-4年</span><span class="type_5">招1人</span></p></div>
    <a class="com_name" href="/all/co123.html">示例品牌</a>
    <div class="bmsg job_msg inbox"><div>岗位职责<br><br>构建产品。<br>协同交付。</div>
      <div class="mt10"><p class="fp"><span class="label">职能类别：</span><a>产品经理/主管</a></p></div>
      <div class="clear"></div></div>
    <div class="bmsg inbox"><p class="fp">示例大厦</p><div class="clear"></div>
      <address data-address-country="CN" data-address-region="北京" data-address-locality="北京" class="fp-bottom"><span>地图</span>完整地址：北京示例大厦 </address></div>`;

test('current metadata uses labelled icons, preserving absent degree and full address', async () => {
    const result = await detail(currentJob + currentCompany);
    assert.equal(result.error, undefined);
    const row = result.rows[0];
    assert.equal(row.company, '示例品牌');
    assert.equal(row.companyType, '已上市');
    assert.equal(row.companySize, '10000人以上');
    assert.equal(row.companyIndustry, '在线生活服务(O2O)');
    assert.equal(row.location, '北京');
    assert.equal(row.workYear, '3-4年');
    assert.equal(row.degree, '');
    assert.equal(row.address, '北京示例大厦');
    assert.equal(row.category, '产品经理/主管');
    assert.equal(row.description, '岗位职责\n\n构建产品。\n协同交付。');
});

test('missing structured company fields remain empty without shifting other fields', async () => {
    const company = currentCompany.replace(/<p title="10000人以上"[^>]*>[\s\S]*?<\/p>/, '');
    const row = (await detail(currentJob + company)).rows[0];
    assert.equal(row.companyType, '已上市');
    assert.equal(row.companySize, '');
    assert.equal(row.companyIndustry, '在线生活服务(O2O)');
});

for (const mode of ['plain', 'empty']) {
    test('description retains HTML line breaks with ' + mode + ' detached innerText', async () => {
        const row = (await detail(currentJob + currentCompany, mode)).rows[0];
        assert.equal(row.description, '岗位职责\n\n构建产品。\n协同交付。');
    });
}

test('legacy company tags and labelled address remain supported', async () => {
    const result = await detail(`<div class="cn"><h1>工程师</h1><p class="msg ltype">上海 | 3年 | 本科</p></div>
      <div class="job_msg"><p>设计。</p><p>交付。</p></div>
      <div class="bmsg"><p class="fp">上班地址：示例路1号</p></div>
      <div class="com_tag">国企\n\n150-500人\n\n电子技术/半导体/集成电路</div>`);
    assert.equal(result.error, undefined);
    const row = result.rows[0];
    assert.equal(row.companyType, '国企');
    assert.equal(row.companySize, '150-500人');
    assert.equal(row.companyIndustry, '电子技术/半导体/集成电路');
    assert.equal(row.address, '示例路1号');
    assert.equal(row.degree, '本科');
    assert.equal(row.description, '设计。\n交付。');
});
