import pytest

from regression.taiga_critical_important import test_android_bugs


def test_my_notes_view_metric_assertion_rejects_author_visible_view_count():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="我的笔记" />
      <android.widget.TextView text="骑行让我们出发吧" />
      <android.widget.TextView text="浏览 18" />
    </hierarchy>
    """

    with pytest.raises(AssertionError, match="view metrics"):
        test_android_bugs._assert_my_notes_hide_view_metrics(page_source)


def test_my_notes_view_metric_assertion_allows_comments_and_actions():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="我的笔记" />
      <android.widget.TextView text="骑行让我们出发吧" />
      <android.widget.TextView text="共 0 条评论" />
      <android.widget.TextView text="编辑" />
      <android.widget.TextView text="删除" />
    </hierarchy>
    """

    test_android_bugs._assert_my_notes_hide_view_metrics(page_source)
