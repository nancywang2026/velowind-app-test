# 2026-09-15 iOS 活动场次入口失败

## 范围与当前状态

- 用户要求：分析并修复报告中的失败用例。
- 用例：`test_user_can_add_activity_session_from_my_approved_activity`。
- 模块：`velowind_appium/modules/activity_sessions.py`；iOS 真机。
- 当前状态：真机局部通过（仅此用例）；整套未验证，新增场次未清理；最后核实日期：2026-09-15。
- 历史参考：`activity-session-ios-android-notes.md` 提到 iOS 部分控件需要 W3C touch；不能直接认定本次原因相同。

## 失败证据

- 原运行：`20260915-131118-69816`，目录 `.tmp/appium-ios/runs/20260915-131118-69816/allure-report`。
- 临时 URL：http://127.0.0.1:59938/#suites/939591926e03527b1c0b544223c58491/4ff131558541dc61/
- 步骤：`01-add-activity-session`；报错：`Unable to open Manage Sessions for an approved activity`。
- 附件副本：`.tmp/activity-session-fix/failure.png`、`failure.xml`。
- 截图处于“我的活动 / 发布”，底部“上海出发到杭州2”具有“通过、上架”状态和更多按钮。尚未进入新增场次表单。

## 第 1 轮：分析与验证

- 已确认：当前 `_ios_approved_more_point` 对失败 XML 返回 `(364.0, 780.5)`，位于可见目标按钮内；不能归因于没有合格活动。
- 推测：`mobile: tap` 没有触发菜单；通过同一真机会话对比 mobile tap 与 W3C touch 验证。
- 验证前检查 `ps -axo pid,etime,command`，无 pytest；存在多个常驻 Appium 服务，未终止任何进程。
- 验证命令：`PYTHONPATH=apps/velowind-app/appium .venv/bin/python .tmp/activity-session-fix/probe.py`。
- 探针仅打开列表和菜单，不提交场次；运行中，结果待补充。
- 原用例断言：失败；实际清理：未涉及新增；修复后完整真机用例：未验证。

## 可复用方法与无效尝试

- 先用原报告 XML 验证定位坐标，再比较实际点击方式，避免盲目扩大超时。

## 遗留项与交接

- 待完成：点击对照、针对性修改和回归验证。

### 第 1 轮补充：排除点击失效

- 真机探针完成：找到 `(364, 542)`，`mobile: tap` 后 XML 出现“管理场次”。无需替换点击方式。
- 原运行 timing 文件：`timing/main-69817-1789449079120232000/timings.json`。末段每次 source 约 9.7–10.2 秒，tap-more 段仅约 0.006 秒（未执行设备点击），最后一次 scroll 2.35 秒后退出。与失败截图结合，确认最后滚动的结果未检查。

## 第 2 轮：滚动后检查与回归

- 修改 `_open_ios_manage_sessions`：每次滚动后必读一次新页面，即使滚动跨过截止时间；超时后不再滚动，菜单点击失败或详情恢复后也检查截止时间，避免无限循环。
- 保留同卡片“通过 + 上架”、可见范围校验及原错误断言，不改变活动状态。
- 新增边界回归：最后滚动跨截止时间后目标出现仍能点击；目标未出现时只补一次读取且失败退出。
- 真机探针未创建数据；完整新增场次用例回归已启动，运行 ID `20260915-activity-session-fix`。

### 验证命令与结果

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_ios_p1_performance.py apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py -q
VW_APPIUM_RUN_ID=20260915-activity-session-fix VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/activity/test_manage_activity_session.py -q -s --alluredir=.tmp/appium-ios/runs/20260915-activity-session-fix/allure-results
```

- 单元：142 passed，18.64 秒；1 个现有 urllib3/LibreSSL 警告。`git diff --check` 通过。
- 真机：运行中；不能将单元通过计为真机通过。

### 第 2 轮实际结果（保留失败）

- 真机 `20260915-activity-session-fix`：1 failed，121.28 秒；仍是入口超时，未新增数据。
- 新失败 XML 中没有可见合格活动，只滚动到 9 月 6–8 日的待审活动。最后 source 8.96 秒，入口总耗时 93.44 秒。边界修改本身不足以解决长列表超过 90 秒的问题。

## 第 3 轮：独立查找预算

- 为 `add_activity_session` 增加可选 `manage_timeout`，默认保持原超时；该用例明确传 180 秒，只扩大活动列表查找预算，表单仍为 90 秒。
- 本轮将重跑完整真机用例；保留所有既有可见性和状态断言。
- 另发现用例仍断言固定 `2026-08-01`，而 draft 已使用当天加 15 天；另立记录修复过期断言，避免提交后误报。

### 第 3 轮单元结果

- API 改动后相关两个文件回归仍为 142 passed，18.61 秒。
- 补充默认/指定查找预算的参数化测试时，首次收集因缺少 `pytest` 导入失败；补上导入后 `-k prepares_home`：2 passed，111 deselected。未覆盖或隐去该中间失败。
- 真机回归命令同上一轮，run ID 与 alluredir 改为 `20260915-activity-session-fix-r3`。

### 第 3 轮实际结果与最终交接

- 真机：`20260915-activity-session-fix-r3`，**1 passed，441.19 秒**。入口 106.79 秒，提交 20.65 秒；场次发布检查流程 40.17 秒。106.79 秒实测证实原 90 秒预算不足。
- 报告目录：`.tmp/appium-ios/runs/20260915-activity-session-fix-r3/allure-results`；生成 HTML 位于同级 `allure-report`。
- 原始失败及第 2 轮失败均保留。完整相关单元 142 passed，新增预算参数测试补跑 2 passed；合计覆盖最终 143 个不同单元测试（未宣称最终一次全量运行 143 passed）。
- 数据清理：本用例无自动清理步骤，本轮新增“测试 - 场次 0915”未删除；未验证删除。前两轮入口失败未执行新增。
- 已完成：定位确认、最后滚动检查、独立 180 秒查找预算、日期断言修正、目标真机用例通过。
- 未完成/未验证：整套回归、Android 真机、测试场次删除。查找仍受固定 180 秒上限约束，列表进一步增长时可能再次超时，可另行研究限定测试活动/查询方式。
- 设备状态：本轮 pytest 已退出，会话正常 quit；未停止其他 Appium 服务。
- 下一步：如需整套结论，先检查设备占用后运行对应 suite；不要将此次单用例通过视为整套通过。
