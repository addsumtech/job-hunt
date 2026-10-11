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
const job51Utils = patched('51job/utils.js', fs.readFileSync(path.join(__dirname, 'fixtures/opencli-1.8.7-51job-utils.js.txt'), 'utf8'));
const job51Search = patched('51job/search.js', fs.readFileSync(path.join(__dirname, 'fixtures/opencli-1.8.7-51job-search.js.txt'), 'utf8'));
class CliError extends Error { constructor(code, message) { super(message); this.code = code; } }
const job51 = vm.runInNewContext(job51Utils.replace(/^import.*;$/gm, '').replace(/^export /gm, '') +
    ';({ SALARY_CODES, WORKYEAR_CODES, DEGREE_CODES, COMPANY_TYPE_CODES, COMPANY_SIZE_CODES, SORT_CODES, resolveCode, resolveCity, buildSearchUrl, mapJobItem, requirePage, WE_ORIGIN, SEARCH_COLUMNS })', {CliError, URL, URLSearchParams});

test('51job filters match the dictionaries bound to the actual search UI', () => {
    const captured = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/51job-search-enums-20261011.json'), 'utf8'));
    const tables = {d_search_cottype:'COMPANY_TYPE_CODES', d_search_companysize:'COMPANY_SIZE_CODES',
        d_search_degreefrom:'DEGREE_CODES', d_search_workyear:'WORKYEAR_CODES', d_search_providesalary:'SALARY_CODES'};
    for (const [name, table] of Object.entries(tables)) {
        for (const {code, value} of captured.dictionaries[name]) {
            assert.equal(job51.resolveCode(value, job51[table]), code, value);
            assert.equal(job51.resolveCode(code, job51[table]), code, value);
        }
    }
    assert.equal(job51.resolveCode('国企', job51.COMPANY_TYPE_CODES), '04');
    assert.equal(job51.resolveCode('合资', job51.COMPANY_TYPE_CODES), '03');
    for (const [value, table] of [['外资', 'COMPANY_TYPE_CODES'], ['1年以下', 'WORKYEAR_CODES'],
        ['5-7年', 'WORKYEAR_CODES'], ['3-5万', 'SALARY_CODES'], ['2-3千', 'SALARY_CODES'], ['未知', 'DEGREE_CODES']]) {
        assert.throws(() => job51.resolveCode(value, job51[table]), /Unknown or ambiguous/);
    }
    assert.equal(job51.resolveCode('', job51.COMPANY_TYPE_CODES), '');
});

test('51job sends corrected filter codes and rejects mislabeled state-owned results', async () => {
    let requested;
    const adapter = type => loadAdapter(job51Search, {...job51, CliError,
        pageFetchJson: async (page, url) => { requested = new URL(url); return {status:1, resultbody:{job:{items:[
            {jobId:'172537456', jobName:'行政文秘', companyTypeString:type}]}}}; }}).config;
    const page = {evaluate: async () => 'https://we.51job.com/pc/search'};
    const args = {keyword:'行政', area:'成都', companyType:'国企', experience:'3-5年', salary:'5万以上', limit:3};
    const rows = await adapter('国企').func(page, args);
    assert.equal(requested.searchParams.get('companyType'), '04');
    assert.equal(requested.searchParams.get('workYear'), '03');
    assert.equal(requested.searchParams.get('salary'), '12');
    assert.equal(rows[0].companyType, '国企');
    await assert.rejects(adapter('合资').func(page, args), /non-state-owned/);
    await assert.rejects(adapter('').func(page, args), /unlabeled/);
});
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

// A page whose "About the job" pane holds OTHER text than the requested job's.
// The search layout keeps one detail pane and swaps its contents, so a pane that
// has not caught up still answers readRenderedDescription().
function extractWithPane(payloads, { paneText = '', href = 'https://www.linkedin.com/jobs/search/?currentJobId=123',
    requestedId = '123' } = {}) {
    const codes = payloads.map(included => ({ textContent: JSON.stringify({ included }) }));
    const heading = { innerText: 'About the job', closest: () => ({ innerText: 'About the job ' + paneText }) };
    return vm.runInNewContext(linkedin().tests.buildExtractionScript(requestedId), {
        URL, location: new URL(href),
        document: {
            body: { innerText: 'Search Jobs' }, querySelector: () => null,
            querySelectorAll: selector => selector === 'code[id^="bpr-guid-"]' ? codes
                : selector === 'h1,h2,h3,h4' ? (paneText ? [heading] : []) : [],
        },
    });
}

test('a stale detail pane cannot supply the requested job description', () => {
    // The requested job's top card is present but its description has not loaded.
    // The pane still shows the previously opened job. Measured 2026-10-08: the
    // old code returned that pane text as this job's description, and every
    // downstream provenance check passed it, because the quote really is in the
    // capture and the command line really names the requested id.
    const row = extractWithPane([
        [{ jobPostingTitle: 'Requested role', '*jobPosting': 'urn:li:fsd_jobPosting:123' }],
        [{ entityUrn: 'urn:li:fsd_jobPosting:123' }],
    ], { paneText: 'DESCRIPTION OF A DIFFERENT JOB' });
    assert.ok(!String(row?.description || '').includes('DIFFERENT JOB'),
        'the pane belongs to no verified job; it must not become this job description');
    assert.throws(() => linkedin().tests.normalizeDetail(row), /empty or still loading/);
});

test('a navigation that landed on another job is refused, not described', () => {
    // goto(123) can end on 999 after a redirect. The id was read from
    // location.href AFTER navigation, so every urn then matched 999 and the
    // wrong posting came back as a complete, valid detail.
    const row = extractWithPane([
        [{ entityUrn: 'urn:li:fsd_jobPosting:999', description: { text: 'JD OF JOB 999' } },
            { jobPostingTitle: 'Other role', '*jobPosting': 'urn:li:fsd_jobPosting:999' }],
    ], { href: 'https://www.linkedin.com/jobs/search/?currentJobId=999', requestedId: '123' });
    assert.ok(!String(row?.description || '').includes('JOB 999'),
        'a detail for another posting must never be returned for the requested id');
    assert.throws(() => linkedin().tests.normalizeDetail(row), /another job|empty or still loading/);
});

test('a page carrying no job id at all is refused, not described', () => {
    // normalizeJobUrl always navigates to /jobs/search/?currentJobId=<id>, so a
    // page with neither that parameter nor /jobs/view/<id> is not the posting
    // we asked for — a list page or an interstitial. Without this, its h1 and
    // pane text came back as a complete detail for the requested id.
    const row = extractWithPane([], { href: 'https://www.linkedin.com/jobs/',
        requestedId: '123', paneText: 'TEXT FROM SOME OTHER PAGE' });
    assert.ok(!String(row?.description || '').includes('OTHER PAGE'));
    assert.throws(() => linkedin().tests.normalizeDetail(row), /no job id|another job/);
});
