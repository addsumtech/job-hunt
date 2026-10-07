// Execute the shipped patch code with synthetic payloads, without a browser or
// npm installation. The upstream fixture retains the Apache-2.0 license in
// references/opencli-patches/LICENSE and is checked against the manifest hash.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createHash } = require('node:crypto');
const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, '../../references/opencli-patches/1.8.7.json'), 'utf8'));
const entry = name => manifest.files.find(item => item.path === name);
const digest = value => createHash('sha256').update(value).digest('hex');
const changed = (name, anchor) => entry(name).replacements.find(item => item.old.includes(anchor)).new;

function patched(name, source) {
    const patch = entry(name);
    assert.equal(digest(source), patch.base_sha256);
    for (const { old, new: replacement } of patch.replacements) {
        assert.equal(source.split(old).length - 1, 1);
        source = source.replace(old, replacement);
    }
    assert.equal(digest(source), patch.patched_sha256);
    return source;
}

function loadAdapter(source, extra = {}) {
    let config;
    const context = {
        cli(value) { config = value; }, Strategy: { COOKIE: 'cookie', PUBLIC: 'public' },
        URL, URLSearchParams, ArgumentError: Error, CommandExecutionError: Error,
        normalizeWhitespace: value => String(value || '').replace(/\s+/g, ' ').trim(),
        normalizeHttpUrl: value => value || '',
        assertSafeLinkedinUrl: value => value,
        unwrapEvaluateResult: value => value,
        assertLinkedInAuthenticated: async () => {}, ...extra,
    };
    source = source.replace(/^import[\s\S]*?from ['"][^'"]+['"];\s*/gm, '').replace('export const __test__', 'const __test__');
    const tests = vm.runInNewContext(source + '\n;typeof __test__ === "undefined" ? {} : __test__', context);
    return { config, tests };
}

const linkedinSource = patched('linkedin/job-detail.js', fs.readFileSync(path.join(__dirname, 'fixtures/opencli-1.8.7-linkedin-job-detail.js.txt'), 'utf8'));
const linkedin = extra => loadAdapter(linkedinSource, extra);
const detailSource = patched('nowcoder/detail.js', entry('nowcoder/detail.js').replacements[0].old);
const nowcoder = loadAdapter(detailSource).config;
const numericId = '935872347918069760';
const uuid = '2bee096697104f1abc77998822334455';
const article = { title: 'A complete free article', content: '<p>' + 'Long paragraph. '.repeat(60) + '</p><p>THE END.</p>', createTime: 1791001355000, hasLook: true, showMessage: { showContent: true } };

async function readNowcoder(id, responses, calls = []) {
    const expression = nowcoder.pipeline.find(step => step.evaluate).evaluate.replace('${{ args.id | json }}', JSON.stringify(id));
    return vm.runInNewContext(expression, {
        URL,
        fetch: async url => {
            calls.push(url);
            const next = responses[calls.length - 1];
            assert.ok(next, 'Unexpected extra request');
            return { ok: next.status === undefined || next.status === 200, status: next.status || 200,
                statusText: 'test status', json: async () => {
                    if (next.nonJson) throw new SyntaxError('HTML response');
                    return next.body;
                } };
        },
    });
}

test('LinkedIn search encodes country commas and punctuation only inside values', () => {
    const source = changed('linkedin/search.js', 'function buildVoyagerSearchQuery');
    const { buildVoyagerUrl } = vm.runInNewContext(source + ';({buildVoyagerUrl})', { URLSearchParams });
    const url = buildVoyagerUrl({ keywords: 'C++ (R&D), team!', location: 'Shanghai, China',
        companyIds: ['1', '2'], experienceLevels: ['4'], jobTypes: ['F'], datePostedValues: ['r604800'], remoteTypes: ['3'] }, 10, 2);
    assert.match(url, /keywords:C%2B%2B%20%28R%26D%29%2C%20team%21/);
    assert.match(url, /location:Shanghai%2C%20China/);
    assert.match(url, /company:List\(1,2\),experience:List\(4\),jobType:List\(F\)/);
    assert.match(url, /JobSearchCardsCollection-221/);
    assert.match(url, /&start=10$/);
});

function extractInline(payloads) {
    const codes = payloads.map(included => ({ textContent: JSON.stringify({ included }) }));
    return vm.runInNewContext(linkedin().tests.buildExtractionScript(), {
        URL, location: new URL('https://www.linkedin.com/jobs/search/?currentJobId=123'),
        document: { body: { innerText: 'Search Jobs' }, querySelector: () => null,
            querySelectorAll: selector => selector === 'code[id^="bpr-guid-"]' ? codes : [] },
    });
}

test('LinkedIn joins the requested description across separate inline payloads', () => {
    const row = extractInline([
        [{ entityUrn: 'urn:li:fsd_jobPosting:999', description: { text: 'WRONG JOB' } },
            { jobPostingTitle: 'Other role', '*jobPosting': 'urn:li:fsd_jobPosting:999' }],
        [{ entityUrn: 'urn:li:fsd_jobPosting:123', description: { text: 'Responsibilities\n\nBuild systems.' } }],
        [{ jobPostingTitle: 'Requested role', '*jobPosting': 'urn:li:fsd_jobPosting:123', primaryDescription: { text: 'Example' } }],
    ]);
    assert.equal(row.title, 'Requested role');
    assert.equal(row.description, 'Responsibilities\n\nBuild systems.');
    assert.equal(linkedin().tests.normalizeDetail(row).description, row.description);
});

test('an unrelated inline job description cannot fill the requested empty detail', () => {
    const row = extractInline([
        [{ entityUrn: 'urn:li:fsd_jobPosting:999', description: { text: 'WRONG JOB' } }],
        [{ jobPostingTitle: 'Requested role', '*jobPosting': 'urn:li:fsd_jobPosting:123' }],
    ]);
    assert.equal(row.description, '');
    assert.throws(() => linkedin().tests.normalizeDetail(row), /description is empty/);
});

test('LinkedIn awaits delayed descriptions within a bounded attempt count', async () => {
    let reads = 0;
    const waits = [];
    const result = await linkedin().config.func({ goto: async () => {}, wait: async value => waits.push(value),
        evaluate: async () => ({ title: 'Engineer', description: ++reads === 3 ? 'Complete JD' : '' }) }, { 'job-url': 'https://www.linkedin.com/jobs/view/123/' });
    assert.equal(reads, 3);
    assert.equal(result[0].description, 'Complete JD');
    assert.deepEqual(waits, [4, 2, 2]);
});

test('LinkedIn rejects a persistently blank detail and stops immediately on an auth wall', async () => {
    let reads = 0;
    const page = { goto: async () => {}, wait: async () => {}, evaluate: async () => { reads++; return { title: 'Engineer', description: '' }; } };
    await assert.rejects(linkedin().config.func(page, { 'job-url': 'https://www.linkedin.com/jobs/view/123/' }), /description is empty/);
    assert.equal(reads, 6);
    reads = 0;
    await assert.rejects(linkedin({ assertLinkedInAuthenticated: async () => { throw new Error('login required'); } }).config.func(page,
        { 'job-url': 'https://www.linkedin.com/jobs/view/123/' }), /login required/);
    assert.equal(reads, 0);
});

test('Nowcoder reads numeric IDs and URLs without truncating body or losing createTime', async () => {
    for (const id of [numericId, 'https://www.nowcoder.com/discuss/' + numericId]) {
        const calls = [];
        const [row] = await readNowcoder(id, [{ body: { success: true, data: article } }], calls);
        assert.equal(calls.length, 1);
        assert.match(calls[0], /content-data\/detail\/935872347918069760$/);
        assert.ok(row.content.length > 500);
        assert.match(row.content, /\nTHE END\.$/);
        assert.equal(row.time, '2026-10-03T04:22:35');
        assert.equal(row.content_complete, true);
        assert.equal(row.content_access, 'full');
        assert.equal(row.url, 'https://www.nowcoder.com/discuss/' + numericId);
    }
});

test('Nowcoder keeps restricted previews explicitly incomplete', async () => {
    for (const access of [{ hasLook: false, blogZhuanlan: { id: 'column' } }, { showMessage: { showContent: false } }]) {
        const [row] = await readNowcoder(numericId, [{ body: { success: true, data: { ...article, ...access } } }]);
        assert.equal(row.content_complete, false);
        assert.equal(row.content_access, access.blogZhuanlan ? 'paid_preview' : 'restricted');
    }
});

test('Nowcoder uses moment UUIDs and only falls back after an explicit numeric not-found response', async () => {
    const calls = [];
    await readNowcoder(uuid, [{ body: { success: true, data: article } }], calls);
    assert.match(calls[0], new RegExp('moment-data/detail/' + uuid + '$'));
    const fallback = [];
    await readNowcoder(numericId, [{ body: { success: false, msg: '内容不存在' } }, { body: { success: true, data: article } }], fallback);
    assert.equal(fallback.length, 2);
    assert.match(fallback[1], /moment-data\/detail/);
});

test('Nowcoder preserves HTTP and API refusals without trying another endpoint', async () => {
    for (const response of [{ status: 401, body: { msg: 'Login required' } }, { status: 429, body: { msg: 'Rate limited' } }, { body: { success: false, msg: '请完成验证' } }]) {
        const calls = [];
        await assert.rejects(readNowcoder(numericId, [response], calls), /Login required|Rate limited|请完成验证/);
        assert.equal(calls.length, 1);
    }
    await assert.rejects(readNowcoder('https://example.com/discuss/' + numericId, []), /nowcoder.com post URL/);
    for (const status of [401, 429]) {
        const calls = [];
        await assert.rejects(readNowcoder(numericId, [{ status, nonJson: true }], calls), new RegExp('HTTP ' + status));
        assert.equal(calls.length, 1);
    }
});

test('recommendation, experience and search preserve the correct post identity', () => {
    const contentData = { id: numericId, uuid, title: 'Long article' };
    const recommendation = changed('nowcoder/recommend.js', 'item.momentData');
    const experience = changed('nowcoder/experience.js', 'item.contentData');
    assert.equal(vm.runInNewContext(recommendation, { item: { contentData } }), numericId);
    assert.equal(vm.runInNewContext(recommendation, { item: { longContentData: contentData } }), numericId);
    assert.equal(vm.runInNewContext(recommendation, { item: { momentData: { uuid } } }), uuid);
    assert.equal(vm.runInNewContext(experience, { item: { contentData } }), numericId);
    const search = changed('nowcoder/search.js', 'const uuid');
    assert.equal(vm.runInNewContext(search + ';uuid || id', { moment: {}, contentData, data: {} }), numericId);
    assert.equal(vm.runInNewContext(search + ';uuid || id', { moment: { uuid }, contentData: {}, data: {} }), uuid);
});
