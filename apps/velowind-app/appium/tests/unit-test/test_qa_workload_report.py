from __future__ import annotations

from datetime import date

from velowind_appium.qa_workload_report import (
    IssueSummary,
    QACoverageSummary,
    issue_module,
    render_csv_report,
    render_markdown_report,
    should_retry_http_status,
    summarize_issues,
    summarize_qa_coverage,
)


def test_summarize_issues_counts_two_week_defect_workload():
    issues = [
        {
            "subject": "租车支付 - 优惠券支付失败",
            "created_date": "2026-07-20T04:00:00.000Z",
            "modified_date": "2026-07-21T04:00:00.000Z",
            "finished_date": "2026-07-22T04:00:00.000Z",
            "is_closed": True,
            "status_extra_info": {"name": "Closed"},
            "tags": [["bug", None], ["租车", None]],
        },
        {
            "subject": "发布笔记 - 评论状态错误",
            "created_date": "2026-07-23T04:00:00.000Z",
            "modified_date": "2026-07-24T04:00:00.000Z",
            "finished_date": None,
            "is_closed": False,
            "status_extra_info": {"name": "New"},
            "tags": [["ios", None], ["笔记", None]],
        },
        {
            "subject": "活动报名 - 支付方式无法切换",
            "created_date": "2026-07-10T04:00:00.000Z",
            "modified_date": "2026-07-21T04:00:00.000Z",
            "finished_date": "2026-07-21T04:00:00.000Z",
            "is_closed": True,
            "status_extra_info": {"name": "Closed"},
            "tags": [["活动报名", None]],
        },
        {
            "subject": "活动搜索 - 发布者搜索",
            "created_date": "2026-07-28T04:00:00.000Z",
            "modified_date": "2026-07-28T04:00:00.000Z",
            "finished_date": None,
            "is_closed": False,
            "status_extra_info": {"name": "已提交"},
            "tags": [],
        },
    ]

    summary = summarize_issues(
        issues,
        start_date=date(2026, 7, 17),
        end_date=date(2026, 7, 30),
    )

    assert summary.total_issues == 4
    assert summary.created_count == 3
    assert summary.closed_created_count == 1
    assert summary.closed_or_rejected_in_period == 2
    assert summary.submitted_or_ready_count == 1
    assert summary.created_fix_rate == 1 / 3
    assert summary.status_counts == {"Closed": 1, "New": 1, "已提交": 1}
    assert summary.module_rows[0].module == "租车/支付订单"
    assert summary.module_rows[0].created_count == 1
    assert {row.module for row in summary.module_rows} == {
        "租车/支付订单",
        "笔记/评论",
        "活动",
    }


def test_summarize_qa_coverage_uses_non_empty_function_blocks(tmp_path):
    csv_path = tmp_path / "qa.csv"
    csv_path.write_text(
        "\ufeff主功能,功能块,描述,自动化覆盖,详情\n"
        "首页,首页内容流,desc,Partial,detail\n"
        ",首页底部导航栏,desc,Yes,detail\n"
        "活动报名,用户报名参加活动,desc,No,detail\n"
        ",,placeholder,,\n",
        encoding="utf-8",
    )

    summary = summarize_qa_coverage(csv_path)

    assert summary.total_function_points == 3
    assert summary.coverage_counts == {"Partial": 1, "Yes": 1, "No": 1}
    assert summary.full_coverage_rate == 1 / 3
    assert summary.touched_coverage_rate == 2 / 3
    assert summary.weighted_coverage_rate == 0.5
    assert [(row.module, row.total, row.yes, row.partial, row.no) for row in summary.module_rows] == [
        ("首页", 2, 1, 1, 0),
        ("活动报名", 1, 0, 0, 1),
    ]


def test_render_markdown_report_keeps_defects_and_automation_separate():
    issue_summary = IssueSummary(
        total_issues=108,
        created_count=81,
        closed_created_count=47,
        closed_or_rejected_in_period=70,
        submitted_or_ready_count=8,
        created_fix_rate=47 / 81,
        status_counts={"Closed": 47, "New": 14},
        module_rows=[],
    )
    coverage_summary = QACoverageSummary(
        total_function_points=87,
        coverage_counts={"Yes": 11, "Partial": 29, "No": 47},
        full_coverage_rate=11 / 87,
        touched_coverage_rate=40 / 87,
        weighted_coverage_rate=25.5 / 87,
        module_rows=[],
    )

    report = render_markdown_report(
        issue_summary=issue_summary,
        coverage_summary=coverage_summary,
        start_date=date(2026, 7, 17),
        end_date=date(2026, 7, 30),
    )

    assert "## 一、缺陷发现与修复验证" in report
    assert "## 二、自动化测试覆盖" in report
    assert "| 当前缺陷总数 | 108 |" in report
    assert "| 系统功能点总数 | 87 |" in report


def test_render_csv_report_outputs_filterable_sections():
    issue_summary = IssueSummary(
        total_issues=108,
        created_count=81,
        closed_created_count=47,
        closed_or_rejected_in_period=70,
        submitted_or_ready_count=8,
        created_fix_rate=47 / 81,
        status_counts={"Closed": 47, "New": 14},
        module_rows=[],
    )
    coverage_summary = QACoverageSummary(
        total_function_points=87,
        coverage_counts={"Yes": 11, "Partial": 29, "No": 47},
        full_coverage_rate=11 / 87,
        touched_coverage_rate=40 / 87,
        weighted_coverage_rate=25.5 / 87,
        module_rows=[],
    )

    report = render_csv_report(
        issue_summary=issue_summary,
        coverage_summary=coverage_summary,
        start_date=date(2026, 7, 17),
        end_date=date(2026, 7, 30),
    )

    assert "统计周期,,2026-07-17 至 2026-07-30" in report
    assert "缺陷发现与修复验证,指标,当前缺陷总数,108" in report
    assert "自动化测试覆盖,指标,系统功能点总数,87" in report


def test_should_retry_only_transient_http_statuses():
    assert should_retry_http_status(500) is True
    assert should_retry_http_status(502) is True
    assert should_retry_http_status(504) is True
    assert should_retry_http_status(404) is False
    assert should_retry_http_status(401) is False


def test_issue_module_keeps_activity_comments_under_activity():
    assert (
        issue_module({"subject": "活动详情 - 发布评论 输入评论问题", "tags": [["活动", None]]})
        == "活动"
    )
