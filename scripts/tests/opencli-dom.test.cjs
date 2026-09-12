// Optional integration test: run against the actually patched local adapters.
// NODE_PATH=<temporary jsdom install>/node_modules OPENCLI_TEST_ADAPTER_DIR=<clis>
// node --test scripts/tests/opencli-dom.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');
const adapters = process.env.OPENCLI_TEST_ADAPTER_DIR;
assert.ok(adapters, 'Set OPENCLI_TEST_ADAPTER_DIR to the patched adapter directory');

async function extract(name, html, url = 'https://www.indeed.com/viewjob?jk=0123456789abcdef', configure = () => {}) {
    const source = fs.readFileSync(path.join(adapters, 'indeed', name + '.js'), 'utf8');
    const match = source.match(/(?:detail|cards) = await page\.evaluate\(`([\s\S]*?)`\);/);
    assert.ok(match, 'Find the actual browser extraction, not a test reimplementation');
    const dom = new JSDOM(html, { url, runScripts: 'outside-only' });
    Object.defineProperty(dom.window.HTMLElement.prototype, 'innerText', {
        get() { return this.textContent; },
    });
    // Decode JavaScript template-literal escapes before executing the same source.
    const script = new Function('return `' + match[1] + '`')();
    configure(dom.window);
    try { return await dom.window.eval(script); }
    finally { dom.window.close(); }
}
const job = extra => '<h1>Engineer</h1><div id="jobDescriptionText">Build data pipelines.</div>' + extra;

// Synthetic content in the DOM structure observed on Indeed, 2026-09-12.
const currentJob = (description = '<b>Responsibilities</b><p>Build the platform.</p><b>Required skills</b><p>Product experience.</p>') => `
    <h1>Find jobs</h1>
    <div data-testid="desktop-job-header">
      <div><h5 data-testid="vj-job-title">AI Product Manager</h5></div>
      <div data-testid="company-info-metadata"><div>
        <div><a href="/cmp/Example">Example</a><div>3.9</div></div>
        <div><div>New York, NY</div></div>
      </div></div>
      <div><div aria-label="$100,000 a year, Full-time"></div><div>$100,000 a year</div><div>-</div><div>Full-time</div></div>
    </div>
    <div data-testid="viewjob-job-content">
      <div>Match overview: NOT part of the job description.</div>
      <div><h4 data-testid="vj-job-description-heading">Full job description</h4><div>${description}</div></div>
    </div>
    <div>Recommended jobs: NOT part of the job description.</div>`;

test('current detail layout returns the posting fields and only the full description', async () => {
    const result = await extract('job', currentJob());
    assert.equal(result.ready, true);
    assert.equal(result.title, 'AI Product Manager');
    assert.equal(result.company, 'Example');
    assert.equal(result.location, 'New York, NY');
    assert.equal(result.salary, '$100,000 a year');
    assert.equal(result.jobType, 'Full-time');
    assert.equal(result.description, 'ResponsibilitiesBuild the platform.Required skillsProduct experience.');
});

test('a current title with no description is not ready', async () => {
    const result = await extract('job', currentJob(''), undefined, window => {
        window.setTimeout = callback => { callback(); return 0; };
    });
    assert.equal(result.ready, false);
    assert.equal(result.description, '');
});

test('description loading after the current title is awaited', async () => {
    const result = await extract('job', currentJob(''), undefined, window => {
        window.setTimeout(() => {
            window.document.querySelector('[data-testid="vj-job-description-heading"]').nextElementSibling.textContent = 'Loaded complete responsibilities.';
        }, 10);
    });
    assert.equal(result.ready, true);
    assert.equal(result.description, 'Loaded complete responsibilities.');
});

test('current header without a location does not use the employer as its location', async () => {
    const result = await extract('job', currentJob().replace('<div><div>New York, NY</div></div>', ''));
    assert.equal(result.company, 'Example');
    assert.equal(result.location, '');
});

for (const [label, markup, salary, type] of [
    ['type only', '<span>Full-time</span>', '', 'Full-time'],
    ['pay first', '<span>$100,000 a year</span><span>Full-time</span>', '$100,000 a year', 'Full-time'],
    ['type first', '<span>Contract</span><span>$80 an hour</span>', '$80 an hour', 'Contract'],
    ['multiple types', '<span>Part-time</span><span>Contract</span><span>Part-time</span>', '', 'Part-time, Contract'],
    ['missing pay', '', '', ''],
]) {
    test(label + ' keeps pay separate from employment type', async () => {
        const result = await extract('job', job('<div id="salaryInfoAndJobType">' + markup + '</div>'));
        assert.equal(result.salary, salary);
        assert.equal(result.jobType, type);
    });
}

test('labelled job details work without header chips', async () => {
    const result = await extract('job', job('<div id="jobDetailsSection"><div role="group" aria-label="Pay"><li>$90 an hour</li></div><div role="group" aria-label="Job type"><li>Contract</li></div></div>'));
    assert.equal(result.salary, '$90 an hour');
    assert.equal(result.jobType, 'Contract');
});

test('current company header exposes Remote without an old location test id', async () => {
    const result = await extract('job', job('<div data-testid="jobsearch-CompanyInfoContainer"><div><div><div data-testid="inlineHeader-companyName">Example</div></div><div>Remote</div></div></div>'));
    assert.equal(result.location, 'Remote');
});

test('old location selector remains supported without a child div', async () => {
    const result = await extract('job', job('<div data-testid="jobsearch-JobInfoHeader-companyLocation">Boston</div>'));
    assert.equal(result.location, 'Boston');
});

for (const [name, html, url] of [
    ['English login', '<title>Sign In | Indeed Accounts</title><h1>Ready to take the next step?</h1>', 'https://secure.indeed.com/auth'],
    ['localized verification', '<h1>電話番号を確認</h1>', 'https://secure.indeed.com/account/verifyphone'],
]) {
    test(name + ' is not a job', async () => {
        const result = await extract('job', html, url);
        assert.equal(result.loginRequired, true);
        assert.equal(result.description, '');
    });
}

test('login wording inside a real posting is not an interstitial', async () => {
    const result = await extract('job', '<h1>Ready to take the next step?</h1><div id="jobDescriptionText">Sign in to our developer tools.</div>');
    assert.equal(result.loginRequired, false);
});

test('Cloudflare challenge remains detectable', async () => {
    const result = await extract('job', '<title>Just a moment</title><h1>Verify</h1><div id="cf-check"></div>');
    assert.equal(result.challenge, true);
});

test('search title does not depend on the removed nested span', async () => {
    const result = await extract('search', '<div class="job_seen_beacon"><h2><a class="jcs-JobTitle" data-jk="0123456789abcdef">Python Engineer</a></h2><div data-testid="company-name">Example</div></div>');
    assert.equal(result.cards.length, 1);
    assert.equal(result.cards[0].title, 'Python Engineer');
});

test('search retains the original title attribute variant and deduplicates ids', async () => {
    const card = '<div class="job_seen_beacon"><h2 class="jobTitle"><a data-jk="0123456789abcdef"><span title="Data Engineer">Data Engineer</span></a></h2></div>';
    const result = await extract('search', card + card);
    assert.equal(result.cards.length, 1);
    assert.equal(result.cards[0].title, 'Data Engineer');
});
