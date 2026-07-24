# iOS Bug Recording Design

## Goal

Add a lightweight, reliable iOS real-device bug recording flow for Appium. The tester operates the app directly on the iPhone, records only meaningful screen states from the terminal, and receives a reviewable bug report first. After the report is confirmed, the tool asks whether to generate an Appium pytest script from the same recording.

The first implementation targets one recording session per bug. It should optimize for clear reproduction evidence, low manual effort, and compatibility with the existing Appium artifact layout.

## User Flow

The recorder starts through the existing iOS recording entry point with a bug mode:

```bash
pnpm appium:ios:record -- --mode bug --session-name search-loading
```

After Appium connects to the real device, the tester manually drives the app on the phone. The terminal accepts lightweight commands:

```text
capture
capture 打开搜索页
actual 页面一直加载中
expected 应展示搜索结果或错误态
note 偶发，第二次复跑通过
done
```

`capture` records the current screen state. If the user provides text after `capture`, that text becomes the reproduction step description. If the description is omitted, the recorder derives a draft description from visible page titles, short visible text, and accessibility identifiers.

At `done`, the recorder enters a short review phase. It prints the captured steps with indexes and draft titles, then lets the tester keep them as-is, rename a step, or delete noisy captures. The review phase must be optional so a fast path can finish with one confirmation.

## Outputs

Each session writes into the existing recording tree:

```text
.tmp/appium-ios/recordings/<session-name>/
  recording.json
  bug-report.md
  taiga-issue.md
  00-initial.png
  00-initial.xml
  01-open-search-page.png
  01-open-search-page.xml
```

`recording.json` remains the machine-readable source of truth. It stores session metadata, environment metadata, expected and actual result text, notes, and an ordered list of captured states. Each captured state includes its label, optional user description, generated description, screenshot path, XML path, page-source hash, visible identifiers, and visible short text.

`bug-report.md` is the human-readable artifact for review. It includes:

- title and session name
- device, iOS/Appium configuration, bundle id, UDID, and recording time
- reproduction steps from the reviewed captures
- expected result
- actual result
- notes
- evidence screenshots and XML paths
- link to the raw `recording.json`

`taiga-issue.md` is the exact Markdown body that will be sent to Taiga if the user chooses to create an issue.

## Taiga Integration

After the bug report is generated, the tool asks whether to create a Taiga issue. If confirmed, it uses the Taiga MCP `create_issue` tool with the configured project, generated subject, generated description, and tags such as `ios`, `appium-recording`, and `manual-repro`.

The available Taiga MCP tools do not currently expose file attachment upload. The first version writes screenshot and XML paths into the issue description instead of uploading image files. The Taiga integration should be isolated behind a small adapter so an attachment upload step can be added later without changing recording or report generation.

Project selection can be passed with `--taiga-project <project-slug-or-id>`. If omitted, the recorder still creates local artifacts and skips Taiga creation unless a project is supplied interactively.

## Script Generation Handoff

Bug mode is report-first. After the user confirms the bug report, the tool asks:

```text
是否基于这份 recording 生成 Appium pytest 脚本草稿？[y/N]
```

Only a positive answer invokes the existing generated-test path. The generated script should reuse the reviewed step names and captured page summaries as wait assertions. This keeps B and A connected while preventing premature test-script generation before the bug report is reviewed.

## Architecture

Extend `velowind_appium.ios_manual_recording` instead of creating a separate recorder. The module already owns Appium connection setup, snapshot capture, recording payloads, and the existing `pnpm appium:ios:record` entry point.

Add a bug recording branch selected by `--mode bug`. The default mode remains the current action-command recording behavior to preserve compatibility.

Recommended module boundaries:

- `ios_manual_recording.py`: CLI parsing, driver lifecycle, interactive bug recording loop.
- `bug_recording.py`: bug-specific data classes, command parsing, review flow, description generation, and report body rendering.
- `taiga_reporting.py`: optional Taiga issue body preparation and MCP-facing adapter boundary.
- `generate_ios_test_from_recording.py`: continue to handle pytest generation, reading any reviewed step metadata if present.

The first implementation can keep Taiga issue creation user-assisted if direct MCP invocation from the CLI is not available. In that case, the CLI writes `taiga-issue.md`, and Codex can create the issue through MCP after the user confirms.

## Capture Semantics

The recorder captures the initial state automatically. Each later `capture` stores:

- screenshot via the existing `capture_debug_artifacts`
- XML/page source where available
- page-source hash for change detection
- visible identifiers and visible short text using the existing XML extraction pattern
- generated label suitable for filenames

Repeated captures with the same page-source hash should be allowed, because the tester may want to document a frozen loading state or unchanged failure. The report should mark repeated hashes so the reviewer can see that the screen did not change.

## Review Semantics

The review phase is intentionally small:

```text
Captured steps:
1. 打开搜索页
2. 输入骑行并提交
3. 页面持续显示正在加载

review> keep
review> rename 3 搜索结果持续加载不结束
review> delete 2
```

The first version only needs `keep`, `rename <index> <text>`, and `delete <index>`. Invalid commands should print a concise usage message and return to the review prompt. The review result updates `recording.json` before reports are rendered.

## Error Handling

If Appium cannot capture a screenshot or XML, the step should still be recorded with the error message and any available artifact. A failed capture must not discard earlier steps.

If Taiga creation fails, local report generation remains successful. The CLI should print the local `taiga-issue.md` path and the error so the issue can be created manually or retried later.

If pytest script generation fails after B is complete, the bug report remains valid. Script generation errors are reported separately from recording/reporting errors.

## Testing

Add unit coverage for:

- bug command parsing for `capture`, `actual`, `expected`, `note`, and `done`
- generated description fallback from visible text and identifiers
- review command parsing and mutation
- `recording.json` payload shape for bug mode
- `bug-report.md` and `taiga-issue.md` rendering
- `--mode bug` CLI dispatch without starting a real Appium session

Manual verification should run the iOS recorder against a real device, capture at least three states, generate a local report, and confirm the generated Markdown contains the screenshot paths and reviewed reproduction steps.
