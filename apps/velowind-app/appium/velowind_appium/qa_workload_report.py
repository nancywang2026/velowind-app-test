from __future__ import annotations

import argparse
import csv
from io import StringIO
from collections import Counter, OrderedDict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
import re
from time import sleep
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence
from urllib import parse, request
from urllib.error import HTTPError, URLError


DEFAULT_QA_CSV = Path("/Users/test/Downloads/QA工作簿 (3)-自动化覆盖标注.csv")
DEFAULT_TAIGA_ENV = Path(".tmp/taiga/taiga.env")


@dataclass(frozen=True)
class IssueModuleRow:
    module: str
    created_count: int
    open_count: int
    focus: str


@dataclass(frozen=True)
class IssueSummary:
    total_issues: int
    created_count: int
    closed_created_count: int
    closed_or_rejected_in_period: int
    submitted_or_ready_count: int
    created_fix_rate: float
    status_counts: Mapping[str, int]
    module_rows: Sequence[IssueModuleRow]


@dataclass(frozen=True)
class QAModuleRow:
    module: str
    total: int
    yes: int
    partial: int
    no: int
    weighted_rate: float
    focus: str


@dataclass(frozen=True)
class QACoverageSummary:
    total_function_points: int
    coverage_counts: Mapping[str, int]
    full_coverage_rate: float
    touched_coverage_rate: float
    weighted_coverage_rate: float
    module_rows: Sequence[QAModuleRow]


MODULE_FOCUS = {
    "笔记/评论": "发布、详情、评论、点赞、分享、审核状态",
    "租车/支付订单": "支付方式、优惠券、退款、补差价、费用明细",
    "活动": "搜索、上下架、评论、发布与编辑",
    "活动报名": "报名、支付、状态一致性、取消退款",
    "活动场次": "场次编辑、上下架限制、时间规则",
    "系统/稳定性": "崩溃优化、隐私政策、接口一致性",
    "我的": "身份信息、个人入口、我的活动/租车状态",
    "首页": "首页入口、分类、推荐内容展示",
    "其他/未标注": "补充标签，明确模块归属",
}


QA_FOCUS = {
    "首页": "字段完整性、推荐排序",
    "笔记": "草稿、评论回复/删除、详情字段",
    "租车": "价格日历、订单详情、合同、履约材料",
    "活动": "搜索、草稿、编辑、上下架、评论",
    "活动报名": "报名、实名、支付、审核、退款",
    "活动场次": "编辑、上下架、场次详情",
    "消息": "消息详情",
    "我的": "个人资料、我的活动、卡券",
    "账号与认证": "登录、密码、退出、注销",
}


def load_env_file(path: Path) -> Dict[str, str]:
    path = resolve_input_path(path)
    env: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip("\"'")
    return env


def resolve_input_path(path: Path) -> Path:
    if path.is_absolute() or path.exists():
        return path
    for parent in [Path.cwd()] + list(Path.cwd().parents):
        candidate = parent / path
        if candidate.exists():
            return candidate
    return path


def derive_taiga_api_url(taiga_url: str) -> str:
    if "/api/v1" in taiga_url:
        return taiga_url.rstrip("/")

    parsed = parse.urlparse(taiga_url)
    prefix = ""
    path = parsed.path
    taiga_index = path.find("/taiga")
    if taiga_index >= 0:
        prefix = path[: taiga_index + len("/taiga")]
    return parse.urlunparse((parsed.scheme, parsed.netloc, prefix + "/api/v1", "", "", "")).rstrip("/")


def derive_project_slug(taiga_url: str) -> str:
    match = re.search(r"/project/([^/]+)/", taiga_url)
    if not match:
        raise ValueError("无法从 TAIGA_URL 中识别项目 slug，请使用类似 /project/velowind-app/issues 的 URL")
    return match.group(1)


def should_retry_http_status(status: int) -> bool:
    return status in {500, 502, 503, 504}


def taiga_api_request(
    url: str,
    *,
    token: Optional[str] = None,
    payload: Optional[Mapping[str, Any]] = None,
    timeout: int = 20,
    max_attempts: int = 3,
) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    method = "GET"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
    if token:
        headers["Authorization"] = "Bearer " + token

    last_error: Optional[BaseException] = None
    for attempt in range(1, max_attempts + 1):
        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            last_error = exc
            if attempt >= max_attempts or not should_retry_http_status(exc.code):
                raise
        except URLError as exc:
            last_error = exc
            if attempt >= max_attempts:
                raise
        sleep(0.6 * attempt)
    if last_error:
        raise last_error
    raise RuntimeError("Taiga API 请求失败")


def fetch_taiga_issues(env_path: Path) -> List[Mapping[str, Any]]:
    env = load_env_file(env_path)
    taiga_url = env["TAIGA_URL"]
    api_url = env.get("TAIGA_API_URL") or derive_taiga_api_url(taiga_url)
    project_slug = env.get("TAIGA_PROJECT") or derive_project_slug(taiga_url)

    auth = taiga_api_request(
        api_url + "/auth",
        payload={
            "type": "normal",
            "username": env["TAIGA_USERNAME"],
            "password": env["TAIGA_PASSWORD"],
        },
    )
    token = auth["auth_token"]
    project = taiga_api_request(
        api_url + "/projects/by_slug?" + parse.urlencode({"slug": project_slug}),
        token=token,
    )

    issues: List[Mapping[str, Any]] = []
    for page in range(1, 100):
        query = parse.urlencode(
            {
                "project": project["id"],
                "page": page,
                "page_size": 200,
                "order_by": "status",
            }
        )
        batch = taiga_api_request(api_url + "/issues?" + query, token=token)
        if not batch:
            break
        issues.extend(batch)
        if len(batch) < 200:
            break
    return issues


def parse_taiga_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def period_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(start_date, time.min).replace(tzinfo=timezone(timedelta(hours=8)))
    end = datetime.combine(end_date, time.max).replace(tzinfo=timezone(timedelta(hours=8)))
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def in_period(value: Optional[str], start: datetime, end: datetime) -> bool:
    parsed = parse_taiga_datetime(value)
    return parsed is not None and start <= parsed <= end


def issue_status(issue: Mapping[str, Any]) -> str:
    extra = issue.get("status_extra_info") or {}
    return str(extra.get("name") or issue.get("status") or "未标注")


def issue_module(issue: Mapping[str, Any]) -> str:
    subject = str(issue.get("subject") or "")
    if re.search(r"活动报名|报名费|已报名|重复报名|取消报名|实名报名", subject):
        return "活动报名"
    if re.search(r"场次", subject):
        return "活动场次"
    if re.search(r"租车|订单|取车|还车|补差价|优惠券|支付宝|微信支付|支付中心|支付方式|退款|费用", subject):
        return "租车/支付订单"
    if "活动" in subject:
        return "活动"
    if re.search(r"笔记|评论|点赞|话题|分享笔记|收藏", subject):
        return "笔记/评论"
    if "首页" in subject:
        return "首页"
    if "我的" in subject:
        return "我的"
    if re.search(r"隐私政策|关于我们|崩溃|operations|confirm|前端|样式", subject):
        return "系统/稳定性"

    for tag_value in issue.get("tags") or []:
        tag = tag_value[0] if isinstance(tag_value, list) else tag_value
        tag = str(tag)
        if tag in ("笔记", "笔记详情", "微信"):
            return "笔记/评论"
        if tag == "租车":
            return "租车/支付订单"
        if tag in ("活动", "发布活动"):
            return "活动"
        if tag == "活动报名":
            return "活动报名"
        if tag == "活动场次":
            return "活动场次"
        if tag in ("首页", "我的"):
            return tag
    return "其他/未标注"


def ordered_counter(values: Iterable[str]) -> "OrderedDict[str, int]":
    counts: "OrderedDict[str, int]" = OrderedDict()
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def summarize_issues(
    issues: Sequence[Mapping[str, Any]],
    *,
    start_date: date,
    end_date: date,
) -> IssueSummary:
    start, end = period_bounds(start_date, end_date)
    created = [issue for issue in issues if in_period(issue.get("created_date"), start, end)]
    closed_created = [issue for issue in created if bool(issue.get("is_closed"))]
    closed_or_rejected = [
        issue
        for issue in issues
        if in_period(issue.get("finished_date"), start, end)
        and (bool(issue.get("is_closed")) or issue_status(issue).lower() == "rejected")
    ]
    submitted_or_ready = [
        issue
        for issue in created
        if issue_status(issue) in ("已提交", "Ready for test")
    ]

    module_counts = ordered_counter(issue_module(issue) for issue in created)
    open_module_counts = Counter(issue_module(issue) for issue in created if not bool(issue.get("is_closed")))
    module_rows = [
        IssueModuleRow(
            module=module,
            created_count=count,
            open_count=open_module_counts.get(module, 0),
            focus=MODULE_FOCUS.get(module, "补充专项回归"),
        )
        for module, count in sorted(module_counts.items(), key=lambda item: -item[1])
    ]

    fix_rate = len(closed_created) / len(created) if created else 0.0
    return IssueSummary(
        total_issues=len(issues),
        created_count=len(created),
        closed_created_count=len(closed_created),
        closed_or_rejected_in_period=len(closed_or_rejected),
        submitted_or_ready_count=len(submitted_or_ready),
        created_fix_rate=fix_rate,
        status_counts=ordered_counter(issue_status(issue) for issue in created),
        module_rows=module_rows,
    )


def summarize_qa_coverage(csv_path: Path) -> QACoverageSummary:
    csv_path = resolve_input_path(csv_path)
    rows: List[Dict[str, str]] = []
    current_main = ""
    with csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for raw_row in reader:
            main = (raw_row.get("主功能") or "").strip()
            if main:
                current_main = main
            block = (raw_row.get("功能块") or "").strip()
            if not block:
                continue
            rows.append(
                {
                    "main": current_main,
                    "block": block,
                    "coverage": (raw_row.get("自动化覆盖") or "").strip() or "No",
                }
            )

    coverage_counts = ordered_counter(row["coverage"] for row in rows)
    total = len(rows)
    yes = coverage_counts.get("Yes", 0)
    partial = coverage_counts.get("Partial", 0)

    module_order: "OrderedDict[str, Counter[str]]" = OrderedDict()
    for row in rows:
        module_order.setdefault(row["main"], Counter())[row["coverage"]] += 1

    module_rows = []
    for module, counts in module_order.items():
        module_total = sum(counts.values())
        module_yes = counts.get("Yes", 0)
        module_partial = counts.get("Partial", 0)
        module_no = counts.get("No", 0)
        module_rows.append(
            QAModuleRow(
                module=module,
                total=module_total,
                yes=module_yes,
                partial=module_partial,
                no=module_no,
                weighted_rate=(module_yes + 0.5 * module_partial) / module_total if module_total else 0.0,
                focus=QA_FOCUS.get(module, "补齐核心路径断言"),
            )
        )

    return QACoverageSummary(
        total_function_points=total,
        coverage_counts=coverage_counts,
        full_coverage_rate=yes / total if total else 0.0,
        touched_coverage_rate=(yes + partial) / total if total else 0.0,
        weighted_coverage_rate=(yes + 0.5 * partial) / total if total else 0.0,
        module_rows=module_rows,
    )


def percent(value: float) -> str:
    return f"{value:.1%}"


def table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def render_markdown_report(
    *,
    issue_summary: IssueSummary,
    coverage_summary: QACoverageSummary,
    start_date: date,
    end_date: date,
) -> str:
    defect_metrics = table(
        ["指标", "数量/比例", "说明"],
        [
            ["当前缺陷总数", issue_summary.total_issues, "Taiga 项目全量缺陷"],
            ["近两周新增缺陷", issue_summary.created_count, "测试发现工作量"],
            ["近两周已关闭新增缺陷", issue_summary.closed_created_count, "新增缺陷中已修复关闭"],
            ["新增缺陷修复率", percent(issue_summary.created_fix_rate), f"{issue_summary.closed_created_count} / {issue_summary.created_count}"],
            ["近两周关闭/驳回缺陷", issue_summary.closed_or_rejected_in_period, "修复验证工作量"],
            ["已提交/待测试缺陷", issue_summary.submitted_or_ready_count, "已提交 + Ready for test"],
        ],
    )
    defect_modules = table(
        ["主要模块", "新增缺陷数", "未关闭数", "后续重点"],
        [
            [row.module, row.created_count, row.open_count, row.focus]
            for row in issue_summary.module_rows
        ],
    )

    automation_metrics = table(
        ["指标", "数量/比例", "说明"],
        [
            ["系统功能点总数", coverage_summary.total_function_points, "按 QA 工作簿功能块统计"],
            ["完全覆盖", coverage_summary.coverage_counts.get("Yes", 0), "Yes"],
            ["部分覆盖", coverage_summary.coverage_counts.get("Partial", 0), "Partial"],
            ["未覆盖", coverage_summary.coverage_counts.get("No", 0), "No"],
            ["完全覆盖率", percent(coverage_summary.full_coverage_rate), "Yes / 总功能点"],
            ["已触达覆盖率", percent(coverage_summary.touched_coverage_rate), "(Yes + Partial) / 总功能点"],
            ["折算覆盖率", percent(coverage_summary.weighted_coverage_rate), "Partial 按 0.5 折算"],
        ],
    )
    automation_modules = table(
        ["模块", "功能点", "Yes", "Partial", "No", "折算覆盖率", "后续补强"],
        [
            [
                row.module,
                row.total,
                row.yes,
                row.partial,
                row.no,
                percent(row.weighted_rate),
                row.focus,
            ]
            for row in coverage_summary.module_rows
        ],
    )

    return "\n\n".join(
        [
            f"# 两周测试工作量汇报（{start_date.isoformat()} 至 {end_date.isoformat()}）",
            "## 一、缺陷发现与修复验证",
            defect_metrics,
            defect_modules,
            "## 二、自动化测试覆盖",
            automation_metrics,
            automation_modules,
            "## 汇报总结",
            table(
                ["方向", "总结"],
                [
                    [
                        "缺陷工作量",
                        f"两周新增缺陷 {issue_summary.created_count} 条，关闭/驳回验证 {issue_summary.closed_or_rejected_in_period} 条，主要集中在 "
                        + "、".join(row.module for row in issue_summary.module_rows[:3])
                        + "。",
                    ],
                    [
                        "自动化工作量",
                        f"已梳理 {coverage_summary.total_function_points} 个系统功能点，自动化已触达 {coverage_summary.coverage_counts.get('Yes', 0) + coverage_summary.coverage_counts.get('Partial', 0)} 个，后续重点补齐低覆盖模块。",
                    ],
                ],
            ),
            "",
        ]
    )


CSV_HEADERS = [
    "部分",
    "表格",
    "项目",
    "数量/比例",
    "说明",
    "新增缺陷数",
    "未关闭数",
    "功能点",
    "Yes",
    "Partial",
    "No",
    "折算覆盖率",
    "后续重点/补强",
    "总结",
]


def render_csv_report(
    *,
    issue_summary: IssueSummary,
    coverage_summary: QACoverageSummary,
    start_date: date,
    end_date: date,
) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_HEADERS, lineterminator="\n")
    writer.writeheader()

    def write_row(**values: Any) -> None:
        writer.writerow({header: values.get(header, "") for header in CSV_HEADERS})

    write_row(部分="统计周期", 项目=f"{start_date.isoformat()} 至 {end_date.isoformat()}")

    defect_section = "缺陷发现与修复验证"
    defect_metrics = [
        ("当前缺陷总数", issue_summary.total_issues, "Taiga 项目全量缺陷"),
        ("近两周新增缺陷", issue_summary.created_count, "测试发现工作量"),
        ("近两周已关闭新增缺陷", issue_summary.closed_created_count, "新增缺陷中已修复关闭"),
        ("新增缺陷修复率", percent(issue_summary.created_fix_rate), f"{issue_summary.closed_created_count} / {issue_summary.created_count}"),
        ("近两周关闭/驳回缺陷", issue_summary.closed_or_rejected_in_period, "修复验证工作量"),
        ("已提交/待测试缺陷", issue_summary.submitted_or_ready_count, "已提交 + Ready for test"),
    ]
    for item, value, note in defect_metrics:
        write_row(部分=defect_section, 表格="指标", 项目=item, **{"数量/比例": value, "说明": note})
    for row in issue_summary.module_rows:
        write_row(
            部分=defect_section,
            表格="主要模块",
            项目=row.module,
            新增缺陷数=row.created_count,
            未关闭数=row.open_count,
            **{"后续重点/补强": row.focus},
        )

    automation_section = "自动化测试覆盖"
    automation_metrics = [
        ("系统功能点总数", coverage_summary.total_function_points, "按 QA 工作簿功能块统计"),
        ("完全覆盖", coverage_summary.coverage_counts.get("Yes", 0), "Yes"),
        ("部分覆盖", coverage_summary.coverage_counts.get("Partial", 0), "Partial"),
        ("未覆盖", coverage_summary.coverage_counts.get("No", 0), "No"),
        ("完全覆盖率", percent(coverage_summary.full_coverage_rate), "Yes / 总功能点"),
        ("已触达覆盖率", percent(coverage_summary.touched_coverage_rate), "(Yes + Partial) / 总功能点"),
        ("折算覆盖率", percent(coverage_summary.weighted_coverage_rate), "Partial 按 0.5 折算"),
    ]
    for item, value, note in automation_metrics:
        write_row(部分=automation_section, 表格="指标", 项目=item, **{"数量/比例": value, "说明": note})
    for row in coverage_summary.module_rows:
        write_row(
            部分=automation_section,
            表格="模块覆盖",
            项目=row.module,
            功能点=row.total,
            Yes=row.yes,
            Partial=row.partial,
            No=row.no,
            折算覆盖率=percent(row.weighted_rate),
            **{"后续重点/补强": row.focus},
        )

    write_row(
        部分="汇报总结",
        表格="总结",
        项目="缺陷工作量",
        总结=(
            f"两周新增缺陷 {issue_summary.created_count} 条，关闭/驳回验证 "
            f"{issue_summary.closed_or_rejected_in_period} 条，主要集中在 "
            + "、".join(row.module for row in issue_summary.module_rows[:3])
            + "。"
        ),
    )
    write_row(
        部分="汇报总结",
        表格="总结",
        项目="自动化工作量",
        总结=(
            f"已梳理 {coverage_summary.total_function_points} 个系统功能点，自动化已触达 "
            f"{coverage_summary.coverage_counts.get('Yes', 0) + coverage_summary.coverage_counts.get('Partial', 0)} 个，后续重点补齐低覆盖模块。"
        ),
    )
    return output.getvalue()


def default_date_range(today: Optional[date] = None) -> tuple[date, date]:
    end = today or datetime.now(timezone(timedelta(hours=8))).date()
    return end - timedelta(days=13), end


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    start_default, end_default = default_date_range()
    parser = argparse.ArgumentParser(description="生成两周测试工作量表格汇报，支持 Markdown 或 CSV。")
    parser.add_argument("--taiga-env", type=Path, default=DEFAULT_TAIGA_ENV, help="Taiga 登录配置 env 文件")
    parser.add_argument("--qa-csv", type=Path, default=DEFAULT_QA_CSV, help="QA 自动化覆盖标注 CSV")
    parser.add_argument("--start-date", type=date.fromisoformat, default=start_default, help="统计开始日期，YYYY-MM-DD")
    parser.add_argument("--end-date", type=date.fromisoformat, default=end_default, help="统计结束日期，YYYY-MM-DD")
    parser.add_argument("--issues-json", type=Path, help="可选：使用本地 Taiga issues JSON，跳过在线拉取")
    parser.add_argument("--output", type=Path, help="可选：输出文件路径；后缀为 .csv 时生成 CSV，否则生成 Markdown")
    return parser.parse_args(argv)


def load_issues_json(path: Path) -> List[Mapping[str, Any]]:
    path = resolve_input_path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "issues" in data:
        return data["issues"]
    if isinstance(data, list):
        return data
    raise ValueError("issues JSON 必须是 issue 数组，或包含 issues 字段的对象")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    issues = load_issues_json(args.issues_json) if args.issues_json else fetch_taiga_issues(args.taiga_env)
    issue_summary = summarize_issues(issues, start_date=args.start_date, end_date=args.end_date)
    coverage_summary = summarize_qa_coverage(args.qa_csv)
    render_csv = args.output is not None and args.output.suffix.lower() == ".csv"
    if render_csv:
        report = render_csv_report(
            issue_summary=issue_summary,
            coverage_summary=coverage_summary,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    else:
        report = render_markdown_report(
            issue_summary=issue_summary,
            coverage_summary=coverage_summary,
            start_date=args.start_date,
            end_date=args.end_date,
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        encoding = "utf-8-sig" if render_csv else "utf-8"
        args.output.write_text(report, encoding=encoding)
        print(str(args.output))
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
