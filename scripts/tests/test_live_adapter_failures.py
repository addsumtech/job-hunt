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
