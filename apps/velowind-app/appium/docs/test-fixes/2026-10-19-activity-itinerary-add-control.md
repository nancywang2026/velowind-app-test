# 2026-10-19 活动行程加号控件取整差异

## 范围与当前状态

- 用户要求：所有自动化 case 通过；用例 `test_user_can_publish_activity_for_review`。
- iPhone 17 / App 1.3.0 build 64 / dev-api；最后核实 2026-10-19。
- 当前状态：90 单元通过，真机复验待执行。历史索引无同类行程加号问题。

## 失败证据

- 运行 `20261019-device-test-full-r1`，目录 `.tmp/appium-ios/runs/20261019-device-test-full-r1/`，无临时 URL。
- `02-publish-activity-for-review` 272.7 秒失败：`Unable to add activity itinerary segment at index 1`。
- 截图 `allure-results/d9cbd8ac-8c89-47fd-b78f-985e3b6e69a0-attachment.png`；XML `c4b4ee4e-5b39-4f10-b14f-d63133fc00f1-attachment.xml`。
- 当前在“编辑活动行程”，第一段已填完整，加号清晰可见。
- XML 加号父控件为 `XCUIElementTypeOther (346,361,31,30)`；旧本地筛选和远程 XPath 均要求精确 30 × 30，因此遗漏。

## 第 1 轮：分析、修改与验证

- `activity.py`：本地加号定位和 XPath 均接受 29–31 像素，允许 iOS 取整误差；不改按钮选择顺序及新增后的段数增加验证。
- 原加号单元参数化 30×30、31×30、30×31 三种尺寸。
- 单元命令：`VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_activity_helpers.py -q`，90 passed，5.23 秒；既有 LibreSSL warning。计时目录 `.tmp/appium-ios/runs/20261019-160304-29057/timing/`。
- 真机：未复跑，等待当前 suite 结束；原失败发生在提交前，尚未创建远端活动。
- 实际清理：未执行；失败表单的本地草稿状态尚未核实。
- 本轮无失败修改尝试。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| 固定 30 × 30 控件尺寸 | 原设备 XML 恰为 30 × 30 | 新设备 31 × 30 时完全遗漏，应保留窄范围取整容差 |

## 遗留项与交接

- 复跑完整发布活动用例，不能以离线定位成功代替活动提交成功。

## 第 2 轮：按用户建议优先使用控件结构

- 用户询问是否必须按像素定位；本轮继续核实真实 AX 层级，确认可通过结构识别添加行。
- 当前行程字段组依次包含标题 TextField、副标题 TextField、正文 TextView；紧随的兄弟行只有一个添加控件。优先根据该结构定位，再读取控件实际边界执行点击；不要求固定尺寸。
- 29–31 像素规则只作为旧层级回退保留，结构识别成功时不扫描其他同尺寸控件。
- 新增 36×28 控件测试并加入更靠后的无关 30×30 控件，验证不会回退误选；原失败 XML 实际定位中心 (361,376)，与真实加号一致。
- 首次结构单元重跑 90 passed / 1 failed，5.34 秒：新分支把 XML 字符串尺寸直接与整数比较，触发 TypeError；修正为显式 float。没有将该失败覆盖为成功。
- 同时核实真实字段组含多层单子节点包装；初次真实 XML 定位成功实际仍可能来自尺寸回退，不能作为结构分支已验证的结论。本轮增加逐层解包。
- 最终活动单元 91 passed，5.28 秒；计时目录 `.tmp/appium-ios/runs/20261019-160615-29577/timing/`。
- 为独立验证结构分支，将原失败 XML 的加号尺寸仅在内存改为 36×28（尺寸回退不接受），仍正确选择中心 (364,375)，确认结构识别实际生效；未修改原始证据文件。
- 真机仍需当前 suite 结束后复验。
