# 2026-11-09 iOS 锁屏阻止建立会话

## 范围与当前状态

- 用户要求：分析报告中的新失败，处理后按指定完整命令真机验证。
- 用例：ios-p1.yaml，原失败 test_user_can_publish_note_for_review[publish-note-changbaishan]。
- 平台：iOS 26.2.1 物理 iPhone；生产环境，API 清理。
- 当前状态：原失败已确认锁屏；用户手动解锁后完整命令验证中。
- 最后核实时间：2026-11-09，Asia/Shanghai。
- 历史参考：[共用环境配置](2026-11-07-ios-shared-environment-config.md)、[AI 反馈](2026-11-07-triage-cli-allure-feedback.md)。本次不是上次登录 HTTP 400，原失败尚未执行测试主体及清理。

## 失败证据

- run ID `20261109-174744-98169`；报告 `.tmp/appium-ios/runs/20261109-174744-98169/allure-report/`，原 URL `http://127.0.0.1:64912/#suites/a315921332822b24a92de7455c3da80b/688365f62952738a/`。
- driver fixture 建会话失败，iOS 返回 FBSOpenApplicationErrorDomain Code=7、Locked、Unable to launch because device was not/could not be unlocked。call 未执行，未进入 API 登录。
- 原完成标记 `triage_enabled=false`；timing argv 只有 `--maxfail=1`，未开启重试的 `--maxfail=0`，报告无 AI 附件。说明该次进程实际参数与用户预期不符，原环境变量具体值及来源未知，不推断是谁关闭。
- devicectl lockState 确认 passcodeRequired=true；Appium 服务 4723 ready，无其他 pytest 活跃。未替换其他会话、未终止现有服务。

## 第 1 轮：分析、处置与验证

### 分析与处置

- 已确认直接阻塞是锁屏；没有通过修改断言、超时或跳过处理。用户已手动解锁。
- 原漏入队结果补导入任务 `a615ec90bfe34bf4aace27f670cf9f43`，供既有 worker 分析/回写，不重新执行该原结果。
- 未修改账号或测试代码；既有配置解析修复保留。

### 验证（进行中）

从仓库根目录执行用户指定命令，stdout/stderr 保存至 `.tmp/appium-ios-verify-20261109/full-run.log`：

```bash
VW_APPIUM_TRIAGE_ENABLED=true \
VW_API_ENV=prod \
VW_NOTE_CLEANUP_MODE=api \
VW_APPIUM_RETRY_FAILED=1 \
VW_APPIUM_PLATFORM=ios \
VW_APPIUM_SERVER_URL=http://127.0.0.1:4723 \
VW_IOS_UDID=00008150-0006799C2693401C \
VW_APPIUM_ARTIFACT_DIR=.tmp/appium-ios-device \
pnpm appium:ios:test:suite apps/velowind-app/appium/test-suites/ios-p1.yaml
```

- 启动输出确认入队开启、AI worker 已运行，已建立会话，第一用例发布步骤执行中。
- 同参数只读配置检查确认选择 ios-appium.prod.yaml，加载后的用户名和密码与生产文件相同，清理模式 api，地址 prod-api；未输出凭据。
- 单元测试：本轮未修改代码，未新增运行。
- 真机完整命令：进行中，不能称通过。
- 实际清理：进行中，不能从已进入发布步骤推断清理成功。

## 可复用方法与无效尝试

| 方法 | 结果与边界 |
| --- | --- |
| 只凭“又失败”套用旧密码根因 | 本次是建立会话前的锁屏，必须检查原报告阶段 |
| 用单元通过代替完整命令 | 本轮执行用户指定真机命令，逐项核实业务清理 |

## 遗留项与交接

- 等待完整执行及可能的失败重试，分别记录用例结果、清理结果、AI 入队/诊断情况。
- 锁屏不能靠脚本获知或绕过密码；本次由用户解锁。未更改设备自动锁屏设置。


### 第 1 轮进展：图片发布与清理通过

- 新 run ID `20261109-174955-98455`，首条图片发布 196.5s、API 清理 0.5s，原始 Allure 结果 passed。
- `publish-note-cleanup-result` 明确 deleted 列表含目标标题、skipped=[]，本轮图片新增笔记已删除。不是仅凭步骤 passed 推断删除。
- 目前进入相册视频用例，整套仍未完成。
- 发现命令行同时包含 `--maxfail=0 --maxfail=1`：runner 的重试全失败策略可能被 suite 参数覆盖，待本轮结束后检查，不在运行中更改源码。
