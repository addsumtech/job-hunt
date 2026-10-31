// Exercise the actual Apache-2.0 OpenCLI fixture and exact-hash patch offline.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {createHash} = require('node:crypto');
const original = fs.readFileSync(path.join(__dirname, 'fixtures/opencli-1.8.7-boss-detail.js.txt'), 'utf8');
const entry = JSON.parse(fs.readFileSync(path.join(__dirname, '../../references/opencli-patches/1.8.7.json')))
    .files.find(item => item.path === 'boss/detail.js');
const hash = text => createHash('sha256').update(text).digest('hex');
assert.equal(hash(original), entry.base_sha256);
let patched = original;
for (const change of entry.replacements) {
    assert.equal(patched.split(change.old).length - 1, 1);
    patched = patched.replace(change.old, change.new);
}
assert.equal(hash(patched), entry.patched_sha256);
const id = 'example_security-id';
const url = `https://www.zhipin.com/job_detail/${id}.html`;

function reader(source = patched, options = {}) {
    let config, reads = 0;
    const node = text => ({innerText: text, textContent: text});
    const role = node('Synthetic frontend role');
    const login = {getClientRects: () => options.visibleLogin ? [1] : []};
    const window = {location: {href: url, pathname: new URL(url).pathname}};
    const document = {
        title: options.missingCompany ? 'Synthetic job' : '「Synthetic frontend role招聘」_Synthetic client招聘-BOSS直聘',
        querySelector(selector) {
            if (selector === '.job-sider .sider-company' && options.companyFacts) {
                return {querySelectorAll: () => ['Software', '1000-9999人', 'C轮'].map(node)};
            }
            if (selector === 'h1' || (options.legacy && selector === '.job-primary .name h1')) return role;
            if (selector === '.job-sec-text:not(.fold-text)') {
                return options.missingDescription || reads <= (options.delay || 0)
                    ? null : node('Synthetic responsibilities\nSynthetic complete requirements');
            }
            if (selector === '.job-primary .text-city') return node('Shanghai');
            if (selector === '.job-primary .text-experiece') return node('5 years');
            if (selector === '.job-primary .text-degree') return node('Bachelor');
            if (selector === '.sign-form, .login-card, [class*="login-register"]') return login;
            return null; // A headhunter page has no employer/address blocks.
        },
        querySelectorAll(selector) {
            if (selector === '.sign-form, .login-card, [class*="login-register"]') return [login];
            if (selector === '.job-sider p, .job-sider a[href^="/i"]') {
                return [node('Unrelated recommended employer'), node('Another listed company 上市')];
            }
            return [];
        },
    };
    class AuthRequiredError extends Error {
        constructor(domain, message) { super(message); this.code = 'AUTH_REQUIRED'; }
    }
    class CommandExecutionError extends Error {}
    const context = vm.createContext({
        cli: value => { config = value; }, Strategy: {UI: 'ui'},
        AuthRequiredError, CommandExecutionError, ArgumentError: Error,
        requirePage: page => assert.ok(page), readRequiredString: value => String(value),
        navigateTo: async (page, target, seconds) => { await page.goto(target); await page.wait(seconds); },
        verbose() {}, document, window,
        getComputedStyle: () => ({visibility: options.visibleLogin ? 'visible' : 'hidden'}),
    });
    const executable = source.replace(/^import[\s\S]*?from ['"][^'"]+['"];\s*/gm, '')
        .replace(/^export /gm, '');
    vm.runInContext(executable, context);
    const navigations = [];
    const page = {
        async goto(target) {
            navigations.push(target);
            window.location.href = options.redirect || target;
            window.location.pathname = new URL(window.location.href).pathname;
        },
        async wait() {},
        async evaluate(expression) {
            if (options.evaluateError) throw options.evaluateError;
            if (typeof expression === 'function') { reads++; return expression(); }
            return vm.runInContext(expression, context);
        },
    };
    return {run: () => config.func(page, {'security-id': id}), navigations,
        get reads() { return reads; }};
}

test('original fixture reproduces false AUTH_REQUIRED on the same headhunter DOM', async () => {
    await assert.rejects(reader(original).run(), error => error.code === 'AUTH_REQUIRED');
});

test('plain detail h1, hidden login template and absent optional containers remain readable', async () => {
    const result = reader();
    const [row] = await result.run();
    assert.equal(row.name, 'Synthetic frontend role');
    assert.equal(row.company, 'Synthetic client');
    assert.equal(row.description, 'Synthetic responsibilities\nSynthetic complete requirements');
    assert.equal(row.address, null);
    assert.equal(row.boss_name, null);
    assert.equal(row.industry, null);
    assert.equal(row.stage, null);
    assert.equal(row.url, url);
    assert.deepEqual(result.navigations, [url]);
});

test('legacy title selectors still work without optional address/recruiter blocks', async () => {
    assert.equal((await reader(patched, {legacy: true}).run())[0].name, 'Synthetic frontend role');
});

test('labelled employer metadata is retained when its own company block exists', async () => {
    const [row] = await reader(patched, {companyFacts: true}).run();
    assert.equal(row.industry, 'Software');
    assert.equal(row.scale, '1000-9999人');
    assert.equal(row.stage, 'C轮');
});

for (const options of [{visibleLogin: true}, {redirect: 'https://www.zhipin.com/web/user/login'}]) {
    test(`real login wall stops after one navigation: ${JSON.stringify(options)}`, async () => {
        const result = reader(patched, options);
        await assert.rejects(result.run(), error => error.code === 'AUTH_REQUIRED');
        assert.deepEqual(result.navigations, [url]);
        assert.equal(result.reads, 0);
    });
}

for (const missing of ['missingCompany', 'missingDescription']) {
    test(`incomplete posting is refused without renavigation: ${missing}`, async () => {
        const result = reader(patched, {[missing]: true});
        await assert.rejects(result.run(), error => /complete job posting/.test(error.message)
            && error.code !== 'AUTH_REQUIRED');
        assert.deepEqual(result.navigations, [url]);
        assert.equal(result.reads, 5);
    });
}

test('evaluation failure is preserved rather than swallowed and relabelled as login', async () => {
    const failure = new Error('synthetic CDP execution failure');
    const result = reader(patched, {evaluateError: failure});
    await assert.rejects(result.run(), error => error === failure);
    assert.deepEqual(result.navigations, [url]);
});

test('delayed render is polled within the bound without navigating again', async () => {
    const result = reader(patched, {delay: 2});
    assert.equal((await result.run())[0].company, 'Synthetic client');
    assert.equal(result.reads, 3);
    assert.deepEqual(result.navigations, [url]);
});
