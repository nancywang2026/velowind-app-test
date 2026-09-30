# 2026-09-16 图片发布：权限说明误判为相册已打开

## 范围与当前状态

- 用例：`test_user_can_publish_note_for_review[publish-note-changbaishan]`。
- 真机：`00008150-0006799C2693401C`，报告 target=device，server 4723。
- 当前状态：入口误判及错误提示已修复；用户授予照片权限后，目标真机用例 1 passed，API 实际删除成功。自动切换系统权限的实验代码已撤回。
- 历史参考：[发布详情与清理](2026-09-15-ios-publish-cleanup.md)。本次发生在选图前，不是历史详情误选问题。

## 失败证据

- run：`20260916-095916-95861`；报告 `.tmp/appium-ios/runs/20260916-095916-95861/allure-report/`。
- URL：<http://127.0.0.1:49563/#suites/a315921332822b24a92de7455c3da80b/4360936eff07f8ff/>。
- 失败步骤：`02-publish-note-for-review-publish-note-changbaishan`。
- 报错：`Photo library opened but no selectable photo was found`，尾部建议给模拟器导入图片，不适用于本次真机现场。
- 附件：`data/attachments/54ef71cc485999f.png`、`4efa3ce530e5e5d4.xml`。
- 截图仍在空白发布表单，上方有“相册/本地图片访问权限”和“去开启”；下方有表单未填完整的提示。不是相册空列表画面。

## 第 1 轮：分析与离线复现

- 已确认：`message_detail._note_photo_picker_opened` 对整份 XML 执行子串搜索，包含“从相册选择”就返回 True。
- 实际权限说明文字包含“用于从本机相册选择或从相册选择图片”，命中上述判断，造成相册入口误判。
- 命令环境：`PYTHONPATH=apps/velowind-app/appium .venv/bin/python`；以原失败 XML 作为 FakeDriver.page_source 调用 `_note_photo_picker_opened`，实际返回 **True**。
- `choose_photo_from_library` 在未能打开来源菜单或相册时也返回 False，上层将这些情况一并报成“没有可选照片”，掩盖入口/权限问题。
- 未确认：系统照片权限是尚未申请、已拒绝还是 App 提示状态异常；截图不足以判断。不能据此要求补图片，也不能断言相册为空。
- 本轮无代码修改、未执行单元测试、未真机复跑、未创建业务数据。原失败未到发布成功或清理阶段。

## 遗留项

- 修改相册打开判定为可见具体控件/原生选择器标识，排除权限说明及祖先汇总文本，并用原 XML 场景补回归。
- 真机确认“去开启”的实际行为和系统权限状态，再修正权限处理及选图入口；分开报告相册未打开与相册无目标照片。
- 未发现其他 pytest 进程；本轮未创建或替换会话。

## 第 2 轮：修复与真机验证（进行中）

- 再次复发报告：<http://127.0.0.1:51150/#suites/a315921332822b24a92de7455c3da80b/6f0c3347c7499233/>，仍为真机、相同权限说明误判；原 XML 离线返回 True。
- 用户明确要求修复并真机验证。已检查无其他设备 pytest；本轮单元测试不使用设备。
- 临时现场探测脚本初名 `inspect.py` 遮蔽 Python 标准库 inspect，导入失败，未创建会话；更名 `probe_permission.py` 后运行成功。现场初始发布页无权限提示，点击“去开启”返回 False（按钮当时不存在），不能据此验证权限处理。会话已退出。
- 修改 `message_detail.py`：可见节点的完整属性匹配替代整页子串匹配；隐藏祖先下的节点不计；识别权限说明与“去开启”后点击并处理系统授权，未进入选择器则明确报权限阻塞；取消“相册已打开/模拟器缺图”的无证据错误结论。
- 新增回归：权限说明误判、隐藏节点、真实选择器标识、权限处理成功及阻塞，共 8 项。
- 单元回归进行中，已见失败，待核实原因；不计通过。
- 真机 run `20260916-photo-permission-fix-r1` 进行中，目标为同一图片发布参数用例；尚不计通过。

### 第 2 轮结果（保留失败）

- r1 真机 **1 failed / 39.87 秒**，仍在权限提示页面，未发布。原误导性错误文字已替换，但入口处理未覆盖选择来源后的权限阻塞。
- 初次单元回归 **6 failed / 272 passed**：1 项旧错误文案断言需同步；另 5 项视频单元假驱动受仓库 API 清理配置影响，进入了它们未模拟的 API 清理分支。更新文案断言并用 `VW_NOTE_CLEANUP_MODE=ui` 隔离该单元集后 **278 passed**。真机仍保持仓库 API 清理模式。
- 真机现场进入系统设置，明确看到“寻风集 → 照片 → 无”被勾选；“去开启”会打开设置，不会直接打开照片选择器。现场还显示已有 579 张照片、33 个视频，不能解释为相册为空。
- 更正此前仅点击“去开启”并处理系统弹窗的尝试：已替换为验证系统设置授权并返回被测 App；原做法不能解决已拒绝的权限。

## 第 3 轮：恢复已拒绝权限后重试一次（进行中）

- 在明确检测到被测 App 的相册权限提示时，检查前台 bundle，进入它的系统照片设置，选择完全访问并核对勾选状态，最后返回 App。只允许重新打开和选择目标相册一次，避免无界重试。
- `photo_library_visible` 排除系统设置页，防止设置页 BackButton 被当成相册。
- 补回归验证只重试一次；相关定向单元 **9 passed**。
- 真机 run `20260916-photo-permission-fix-r2` 执行中；尚不计通过。

### 第 3 轮结果（保留失败）

- r2 真机 **1 failed / 50.04 秒**：已进入系统照片设置并点击完全访问，但授权变化重启了 App，读取页面得到空字符串，勾选校验出现 XML ParseError。未发布，未产生清理目标。
- 新增设置页不能当相册、禁止操作其他前台 App 的回归后，单元集 **280 passed**（`VW_NOTE_CLEANUP_MODE=ui`）。

## 第 4 轮：处理授权引起的 App 重启（进行中）

- 授权期间临时把 WDA `defaultActiveApplication` 指向设置，校验完恢复原设置；空快照仅等待，不当作授权成功；返回 App 后重新打开发布页。
- 为验证真实恢复路径，将被测 App 照片权限重新置为“无”，现场证据 `.tmp/photo-picker-investigation/permission-reset.{xml,png}`，然后退出预置会话再运行用例。
- 真机 run `20260916-photo-permission-fix-r3` 执行中，未计通过。

### 第 4 轮结果与用户调整

- r3 **1 failed / 54.34 秒**：系统完全访问勾选状态未确认，未进入发布成功。授权恢复实验未达到可交付状态。
- 补充恢复生命周期单元时发现诊断附件缺少 `attach_text` 导入，首次 **1 failed / 10 passed**，补导入后 **11 passed**；随后这条实验路径随自动授权代码一起撤回，不纳入最终改动。
- 用户明确告知“我给了权限”，随后要求重新跑测试用例。停止重置权限，保留用户授权。
- 撤回未验证成功的自动切换系统授权、回到发布页及重试代码。最终保留：可见完整控件匹配、系统设置不算相册、权限阻塞的明确错误提示，以及相应回归测试。
- r1/r2/r3 均未发布成功，没有本轮新增笔记的清理任务；不覆盖失败记录。

## 第 5 轮：使用用户授予的权限复跑（进行中）

- 真机 run `20260916-photo-permission-fix-r4`，仅重跑 `test_user_can_publish_note_for_review[publish-note-changbaishan]`，无并发设备测试。保持仓库 API 清理配置。
- 最新完整单元回归执行中，使用 `VW_NOTE_CLEANUP_MODE=ui` 隔离旧单元假驱动的清理环境。

### 最终结果

- 真机 r4：**1 passed / 159.10 秒**。首页准备、图片发布、发布后清理三个步骤全部 passed。
- 实际清理：`publish-note-cleanup-result` 为 `deleted=['测试 - 长白山真的有种让人瞬间安静下来的魔力']`、`skipped=[]`；API DELETE 对应 post ID `pst-4196b065d6ad4403bd883ff0a8087259` passed，无 cleanup-pending。
- 最新单元回归：**278 passed / 60.81 秒**；`git diff --check` 通过。
- 报告：`.tmp/appium-ios/runs/20260916-photo-permission-fix-r4/allure-report/`；结果同目录 `allure-results/`。
- 本轮只验证指定图片发布参数用例，未执行整套。真机 pytest 和会话正常退出；保持用户授予的照片权限。
- 本次通过基于用户已授权的环境；未宣称自动修复系统拒绝权限。若权限再次被拒绝，脚本应明确报告权限阻塞，不能误判相册已打开或照片为空。

```bash
VW_NOTE_CLEANUP_MODE=ui VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_message_detail_helpers.py apps/velowind-app/appium/tests/unit-test/test_photo_picker_helpers.py -q

VW_IOS_TARGET=device VW_IOS_UDID=00008150-0006799C2693401C VW_IOS_SHOW_XCODE_LOG=false VW_APPIUM_RUN_ID=20260916-photo-permission-fix-r4 VW_APPIUM_ARTIFACT_DIR=.tmp/appium-ios/runs/20260916-photo-permission-fix-r4/artifacts VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest 'apps/velowind-app/appium/tests/message/test_ios_publish_note.py::test_user_can_publish_note_for_review[publish-note-changbaishan]' -q -s --alluredir=.tmp/appium-ios/runs/20260916-photo-permission-fix-r4/allure-results
```
