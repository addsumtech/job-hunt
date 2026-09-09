"""A captured Indeed refusal, plus synthetic variants that test routing."""
import pathlib

import pytest

import check_opencli_result as classifier
import journal

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = (pathlib.Path(__file__).parent / 'fixtures/indeed-cloudflare.err').read_text()


def test_actual_indeed_cloudflare_response_stops_site():
    result = classifier.classify('indeed', 'search', 1, '', RAW,
                                 signals=classifier.load_signals(classifier.DEFAULT_SIGNALS_FILE))
    assert result['classification'] == 'platform_limit'
    assert result['signal_id'] == 'indeed-cloudflare-challenge'
    assert 'do not retry' in result['remedy']
    assert 'doctor' not in result['remedy']


def test_recognised_challenge_takes_precedence_over_login_hint():
    result = classifier.classify('indeed', 'search', 1, '', RAW + '\nHTTP 403 Forbidden',
                                 signals=classifier.load_signals(classifier.DEFAULT_SIGNALS_FILE))
    assert result['classification'] == 'platform_limit'
    assert result['signal_id'] == 'indeed-cloudflare-challenge'


def test_normal_job_mentioning_challenge_is_not_a_stop():
    result = classifier.classify('indeed', 'search', 0,
        '[{"title":"Engineer: Indeed served a Cloudflare challenge page analysis"}]', '',
        signals=classifier.load_signals(classifier.DEFAULT_SIGNALS_FILE))
    assert result['classification'] == 'ok'


@pytest.mark.parametrize('text', [None, '', 'signals: []', 'signals: wrong',
                                'signals: [wrong]', 'signals: [{pattern: "["}]'])
def test_invalid_stop_signal_configuration_cannot_silently_disable_detection(tmp_path, text):
    p = tmp_path / 'signals.yaml'
    if text is not None:
        p.write_text(text)
    with pytest.raises(journal.YamlUnreadable):
        classifier.load_signals(p)


def test_actual_51job_machine_readable_anti_bot_response_stops_site():
    raw = (pathlib.Path(__file__).parent / 'fixtures/51job-anti-bot.err').read_text()
    result = classifier.classify('51job', 'search', 1, '', raw,
                                 signals=classifier.load_signals(classifier.DEFAULT_SIGNALS_FILE))
    assert result['classification'] == 'platform_limit'
    assert result['signal_id'] == 'opencli-anti-bot'
    assert 'do not retry' in result['remedy']


def test_anti_bot_code_survives_json_output_and_different_wording():
    result = classifier.classify('51job', 'search', 1, '',
                                '{"error":{"code":"ANTI_BOT","message":"request refused"}}')
    assert result['classification'] == 'platform_limit'


@pytest.mark.parametrize('command', ['job', 'detail', 'view'])
@pytest.mark.parametrize('auth_rows', [None, [], [{'site': 'indeed', 'status': 'logged_in'}]])
def test_actual_indeed_sign_in_detail_is_not_a_job(command, auth_rows):
    raw = (pathlib.Path(__file__).parent / 'fixtures/indeed-sign-in-detail.json').read_text()
    result = classifier.classify('indeed', command, 0, raw, '', auth_rows=auth_rows)
    assert result['classification'] == 'not_logged_in'
    assert result['signal_id'] == 'indeed-sign-in-interstitial'
    assert result['row_count'] == 0
    assert not result['empty_result']
    assert not result['needs_detail_recovery']
    assert 'connected browser' in result['remedy']
    assert 'explicit user confirmation' in result['remedy']
    assert 'opencli indeed login' not in result['remedy']


@pytest.mark.parametrize('row', [
    {'title': 'Ready to take the next step?', 'company': 'Example', 'description': ''},
    {'title': 'Ready to take the next step?', 'company': '', 'description': 'Build APIs.'},
    {'title': 'Engineer', 'company': '', 'description': ''},
    {'title': 'Engineer', 'description': 'Ready to take the next step? Sign in to apply.'},
])
def test_real_job_fields_do_not_trigger_sign_in_detection(row):
    import json
    assert classifier.classify('indeed', 'job', 0, json.dumps([row]), '')['classification'] == 'ok'


def test_sign_in_shape_is_scoped_to_indeed_details():
    raw = (pathlib.Path(__file__).parent / 'fixtures/indeed-sign-in-detail.json').read_text()
    for site, command in [('indeed', 'search'), ('linkedin', 'job')]:
        assert classifier.classify(site, command, 0, raw, '')['classification'] == 'ok'


def test_sign_in_detail_stops_later_reads_in_the_same_round():
    import record_browser_capture as browser
    raw = (pathlib.Path(__file__).parent / 'fixtures/indeed-sign-in-detail.json').read_text()
    result = classifier.classify('indeed', 'job', 0, raw, '')
    result['action'] = 'adapter_call'
    assert browser.check_stop_order([
        result, {'action': 'adapter_call', 'site': 'indeed', 'command': 'job'}])
