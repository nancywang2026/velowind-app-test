from unittest.mock import Mock
import subprocess
import pytest
from velowind_api import report_viewer


def test_generate_then_launch_without_blocking(tmp_path, monkeypatch):
    html = tmp_path / 'allure-report'
    html.mkdir()
    generate, launch = Mock(), Mock()
    monkeypatch.setattr(report_viewer.shutil,'which',lambda _: '/bin/allure')
    monkeypatch.setattr(report_viewer.subprocess,'run',generate)
    monkeypatch.setattr(report_viewer.subprocess,'Popen',launch)
    assert report_viewer.open_report(tmp_path/'allure-results',html)
    assert generate.call_args.args[0][1] == 'generate'
    assert launch.call_args.args[0][1] == 'open'
    assert launch.call_args.kwargs['start_new_session'] is True


def test_missing_allure_preserves_results(tmp_path, monkeypatch):
    monkeypatch.setattr(report_viewer.shutil,'which',lambda _: None)
    assert report_viewer.open_report(tmp_path/'results',tmp_path/'report') is False


def test_generation_failure_does_not_open_stale_report(tmp_path, monkeypatch):
    monkeypatch.setattr(report_viewer.shutil,'which',lambda _: '/bin/allure')
    monkeypatch.setattr(report_viewer.subprocess,'run',Mock(side_effect=subprocess.TimeoutExpired('allure',60)))
    launch = Mock()
    monkeypatch.setattr(report_viewer.subprocess,'Popen',launch)
    assert not report_viewer.open_report(tmp_path/'results',tmp_path/'report')
    launch.assert_not_called()


def test_generation_cannot_clean_results(tmp_path, monkeypatch):
    monkeypatch.setattr(report_viewer.shutil,'which',lambda _: '/bin/allure')
    assert not report_viewer.open_report(tmp_path/'results',tmp_path)
