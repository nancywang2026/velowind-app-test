from pathlib import Path

from velowind_appium.cleanup_config import (
    CleanupConfig,
    load_cleanup_config,
    matches_test_data,
)


def test_load_cleanup_config_reads_matcher_arrays(tmp_path, monkeypatch):
    config_file = tmp_path / "cleanup.yaml"
    config_file.write_text(
        """
cleanup:
  note_matchers:
    - "测试 -"
    - "自动化回归"
  activity_matchers:
    - "测试 -"
  session_matchers:
    - "自动化场次"
  comment_matchers:
    - "自动化评论"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("VW_APPIUM_CLEANUP_CONFIG_FILE", str(config_file))

    config = load_cleanup_config()

    assert config == CleanupConfig(
        note_matchers=["测试 -", "自动化回归"],
        activity_matchers=["测试 -"],
        session_matchers=["自动化场次"],
        comment_matchers=["自动化评论"],
    )


def test_load_cleanup_config_uses_safe_defaults(monkeypatch):
    monkeypatch.setenv("VW_APPIUM_CLEANUP_CONFIG_FILE", "/tmp/missing-cleanup.yaml")

    config = load_cleanup_config()

    assert config.note_matchers == []
    assert config.activity_matchers == []
    assert config.session_matchers == []
    assert config.comment_matchers == []


def test_load_cleanup_config_ignores_blank_and_non_string_values(tmp_path, monkeypatch):
    config_file = tmp_path / "cleanup.yaml"
    config_file.write_text(
        """
cleanup:
  note_matchers:
    - "测试 -"
    - ""
    - 123
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("VW_APPIUM_CLEANUP_CONFIG_FILE", str(config_file))

    config = load_cleanup_config()

    assert config.note_matchers == ["测试 -"]


def test_matches_test_data_matches_any_configured_substring():
    assert matches_test_data("测试 - 长白山笔记", ["测试 -", "自动化"]) is True
    assert matches_test_data("普通用户笔记", ["测试 -", "自动化"]) is False
    assert matches_test_data("", ["测试 -"]) is False

