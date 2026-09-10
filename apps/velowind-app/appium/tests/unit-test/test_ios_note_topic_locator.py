from unittest.mock import Mock

import pytest

from velowind_appium.modules import message_detail as notes


def body(value="已填写的内容", **attrs):
    props = dict(visible="true", enabled="true", x="13", y="424", width="376", height="160", value=value)
    props.update(attrs)
    return '<XCUIElementTypeTextView ' + ' '.join(f'{k}="{v}"' for k, v in props.items()) + ' />'


def page(fields, publisher=True):
    title = '<XCUIElementTypeStaticText name="发布笔记"/><XCUIElementTypeStaticText name="存草稿"/>' if publisher else ''
    return '<AppiumAUT>' + title + fields + '</AppiumAUT>'


def test_filled_body_without_placeholder_preserves_content_and_adds_only_missing_topics(monkeypatch):
    element = Mock()
    element.get_attribute.side_effect = lambda name: "短正文 #已有" if name == "value" else None
    driver = Mock(capabilities={"platformName": "iOS"})
    driver.find_element.return_value = element
    monkeypatch.setattr(notes, "_safe_page_source", lambda driver: page(body()))
    write = Mock()
    monkeypatch.setattr(notes, "_replace_text", write)
    monkeypatch.setattr(notes, "_dismiss_editor_keyboard", Mock())
    assert notes._append_note_topics_to_ios_body_by_source(driver, ["#已有", "#新增"])
    write.assert_called_once_with(element, "短正文 #已有 #新增")
    assert driver.find_element.call_count == 1


@pytest.mark.parametrize("source", [
    page(body() + body(y="620")),
    page(body(visible="false")),
    page('<XCUIElementTypeOther visible="false">' + body() + '</XCUIElementTypeOther>'),
    page(body(enabled="false")),
    page(body(), publisher=False),
    '<AppiumAUT>发布笔记 存草稿',
])
def test_ambiguous_hidden_or_nonpublisher_input_preserves_fallback(source, monkeypatch):
    driver = Mock()
    monkeypatch.setattr(notes, "_safe_page_source", lambda driver: source)
    assert notes._find_unique_visible_ios_note_body(driver) is None
    driver.find_element.assert_not_called()


def test_stale_geometry_preserves_fallback(monkeypatch):
    driver = Mock()
    driver.find_element.side_effect = notes.NoSuchElementException()
    monkeypatch.setattr(notes, "_safe_page_source", lambda driver: page(body()))
    assert notes._find_unique_visible_ios_note_body(driver) is None


def test_existing_topics_are_not_written_again(monkeypatch):
    element = Mock()
    element.get_attribute.side_effect = lambda name: "短正文 #已有" if name == "value" else None
    driver = Mock()
    driver.find_element.return_value = element
    monkeypatch.setattr(notes, "_safe_page_source", lambda driver: page(body()))
    write = Mock()
    monkeypatch.setattr(notes, "_replace_text", write)
    monkeypatch.setattr(notes, "_dismiss_editor_keyboard", Mock())
    assert notes._append_note_topics_to_ios_body_by_source(driver, ["#已有"])
    write.assert_not_called()
