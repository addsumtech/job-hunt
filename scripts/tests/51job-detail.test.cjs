// Run against the actual locally patched adapter; no browser or network needed.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const adapters = process.env.OPENCLI_TEST_ADAPTER_DIR;
assert.ok(adapters, 'Set OPENCLI_TEST_ADAPTER_DIR to the patched adapter directory');
let adapter;
class CliError extends Error { constructor(code, message) { super(message); this.code = code; } }
vm.runInNewContext(fs.readFileSync(path.join(adapters, '51job/detail.js'), 'utf8')
    .replace(/^import .*;\s*$/gm, ''), {
    cli: definition => { adapter = definition; }, Strategy: { COOKIE: 'cookie' },
    CliError, URL, JOBS_ORIGIN: 'https://jobs.51job.com', requirePage: () => {},
    navigateTo: async (page, url) => { page.url = url; },
});
const url = 'https://jobs.51job.com/beijing/173521355.html?source=search';
function documentFixture(body = true) {
    const node = text => ({ innerText: text });
    const map = {
        h1: node('APP下载'), '.cn h1': node('AI产品经理'), '.cn strong': node('2.5-5万'),
        '.cn .type_2': node('北京'), '.cn .type_3': node('3年及以上'), '.cn .type_4': node('本科'),
        '.cname a, .tCompany_sidebar .com_msg a, a.com_name': { innerText: 'Example Company', href: 'https://jobs.51job.com/company' },
        '.bmsg.job_msg': { cloneNode: () => ({ innerText: '', textContent: '负责产品规划与交付', querySelectorAll: () => [] }) },
    };
    return { body: body ? node('职位描述') : null,
        querySelector: selector => map[selector] || null, querySelectorAll: () => [] };
}
test('waits for body, uses job heading rather than APP download, and preserves captured URL', async () => {
    let reads = 0, waits = 0;
    const page = {
        evaluate: script => vm.runInNewContext(script, { document: documentFixture(++reads > 1), window: { location: { href: url } } }),
        wait: async () => { waits++; },
    };
    const [result] = await adapter.func(page, { jobId: '173521355', url });
    assert.equal(result.title, 'AI产品经理');
    assert.equal(result.description, '负责产品规划与交付');
    assert.equal(result.location, '北京');
    assert.equal(result.workYear, '3年及以上');
    assert.equal(result.degree, '本科');
    assert.equal(result.company, 'Example Company');
    assert.equal(page.url, url);
    assert.equal(waits, 1);
});
test('missing description cannot pass and waiting is bounded', async () => {
    let reads = 0;
    await assert.rejects(adapter.func({ evaluate: () => { reads++; return { title: 'Job' }; }, wait: async () => {} },
        { jobId: '173521355', url }), /Could not parse/);
    assert.equal(reads, 8);
});
test('verification page stops without retrying', async () => {
    let reads = 0;
    await assert.rejects(adapter.func({ evaluate: () => { reads++; return { error: 'BLOCKED' }; } },
        { jobId: '173521355', url }), /verification/);
    assert.equal(reads, 1);
});
test('unrelated or mismatched URLs are rejected before navigation', async () => {
    for (const bad of ['https://example.com/173521355.html', 'https://jobs.51job.com/beijing/999999999.html']) {
        const page = {};
        await assert.rejects(adapter.func(page, { jobId: '173521355', url: bad }), /matching/);
        assert.equal(page.url, undefined);
    }
});
