"""New refusals guide a human hand-off without weakening the recorded stop."""
import json

import pytest

import check_opencli_result as classifier
import record_browser_capture as browser
from test_browser_fallback import setup_capture, record


def test_login_refusal_tells_user_to_finish_and_continue():
    result = classifier.classify('boss', 'search', 1, '',
        'error: {message: "login required"}',
        auth_rows=[{'site': 'boss', 'status': 'not_logged_in'}])
    assert result['classification'] == 'not_logged_in'
    assert 'finish login' in result['remedy']
    assert 'explicit user confirmation' in result['remedy']
    assert 'new bounded round' in result['remedy']


def test_no_auth_adapter_does_not_invent_a_login_command():
    result = classifier.classify('51job', 'search', 1, '',
        'error: {message: "HTTP 403 Forbidden"}', auth_rows=[])
    assert result['classification'] == 'no_auth_adapter'
    assert 'does not exist' in result['remedy']
    assert 'Do not invent a login command' in result['remedy']
    assert 'inspect the site' in result['remedy']


@pytest.mark.parametrize('message,expected', [
    ('Indeed served a Cloudflare challenge page', 'human verification'),
    ('HTTP 429', 'login is not a fix'),
    ('操作过于频繁', 'login is not a fix'),
    ('访问受限', 'permission or account restriction'),
])
def test_platform_reason_determines_user_action(message, expected):
    result = classifier.classify('indeed', 'search', 1, '',
        json.dumps({'error': {'message': message}}),
        signals=classifier.load_signals(classifier.DEFAULT_SIGNALS_FILE))
    assert result['classification'] == 'platform_limit'
    assert expected in result['remedy']
    assert 'elapsed time is not confirmation' in result['remedy']
    assert 'If refused again, pause and ask again' in result['remedy']


def test_browser_pause_keeps_lock_even_after_recorded_user_message(tmp_path):
    import journal
    ws, _, _, _, args = setup_capture(tmp_path, text='Please sign in to continue')
    call = record(ws, args)
    assert 'explicit user confirmation' in call['remedy']
    assert 'same source and backend' in call['remedy']
    journal.append(ws, {'action': 'user_confirmation', 'message': 'done, continue'})
    assert browser.main(args) == 2
    assert len(browser.read_retrieval_calls(ws)) == 1
    # A confirmation is not an in-journal stop-lock reset, including aliases.
    assert browser.check_stop_order([call, {'action':'browser_call', 'site':'51job.com'}])


def test_new_round_can_capture_then_pauses_again_if_refused(tmp_path):
    old, _, _, _, old_args = setup_capture(tmp_path / 'paused', text='Verify you are human')
    first = record(old, old_args)
    original = (old / 'journal.jsonl').read_bytes()
    new, _, _, _, new_args = setup_capture(tmp_path / 'confirmed')
    (new / 'recovery.md').write_text(
        f'resume_from: {old}\nsite: 51job\nUser: done, continue\n')
    assert record(new, new_args)['classification'] == 'ok'
    assert (old / 'journal.jsonl').read_bytes() == original
    snapshot_path = new / 'raw/51job-refused.json'
    rows_path = new / 'raw/51job-refused-rows.json'
    snapshot_path.write_text(json.dumps({'url':'https://we.51job.com/',
        'retrieved_at':'2026-09-08T10:00:00Z','text':'Verify you are human','links':[]}))
    rows_path.write_text('[]')
    args = ['--workspace',str(new),'--site','51job','--snapshot-file',str(snapshot_path),
        '--rows-file',str(rows_path),'--fallback-reason','unsupported_extraction','--query','Python']
    assert record(new, args)['classification'] == 'platform_limit'
    assert browser.main(new_args) == 2
    assert first['classification'] == 'platform_limit'


def test_browser_rate_limit_does_not_ask_for_login(tmp_path):
    ws, _, _, _, args = setup_capture(tmp_path, text='Too many requests', status=429)
    call = record(ws, args)
    assert 'login is not a fix' in call['remedy']
    assert 'Do not poll' in call['remedy']
