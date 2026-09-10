import os
from pathlib import Path

from velowind_appium.allure_history import prepare_history


def make_run(root: Path, name: str, timestamp: int):
    run = root / 'runs' / name
    results = run / 'allure-results'
    history = run / 'allure-report' / 'history'
    results.mkdir(parents=True)
    history.mkdir(parents=True)
    (history / 'history.json').write_text(name)
    os.utime(results, (timestamp, timestamp))
    os.utime(history, (timestamp, timestamp))
    return results, history.parent


def test_inherits_latest_earlier_report_only_within_platform(tmp_path):
    make_run(tmp_path / 'ios', 'first', 10)
    make_run(tmp_path / 'ios', 'previous', 20)
    results, report = make_run(tmp_path / 'ios', 'current', 30)
    make_run(tmp_path / 'ios', 'future', 40)
    make_run(tmp_path / 'android', 'other-platform', 25)
    prepare_history(results, report)
    assert (results / 'history' / 'history.json').read_text() == 'previous'


def test_regeneration_preserves_original_history(tmp_path):
    make_run(tmp_path, 'previous', 10)
    results, report = make_run(tmp_path, 'current', 20)
    prepare_history(results, report)
    (report / 'history' / 'history.json').write_text('current-output')
    prepare_history(results, report)
    assert (results / 'history' / 'history.json').read_text() == 'previous'


def test_first_report_does_not_inherit_itself(tmp_path):
    results, report = make_run(tmp_path, 'first', 10)
    prepare_history(results, report)
    assert not (results / 'history').exists()


def test_custom_report_uses_platform_latest(tmp_path):
    _, previous = make_run(tmp_path / 'ios', 'previous', 10)
    results, report = make_run(tmp_path / 'custom', 'current', 20)
    latest = tmp_path / 'ios' / 'latest-report'
    latest.symlink_to(previous)
    prepare_history(results, report, latest)
    assert (results / 'history' / 'history.json').read_text() == 'previous'
