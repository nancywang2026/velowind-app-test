# 2026-10-19 首页合并 Button 卡片定位

## 范围与当前状态

- 用户要求：修复所有自动化 case。
- 用例：`test_user_can_comment_on_first_home_note`、`test_user_can_like_and_favorite_second_home_note`。
- iPhone 17 / App 1.3.0 build 64 / dev-api；当前单元验证中，真机复验待执行；最后核实 2026-10-19。
- 历史参考：[短笔记内容](2026-10-10-ios-short-note-content.md)、[详情加载失败](2026-09-21-ios-note-detail-load-failure.md)。本次停在首页，并非详情短标题或加载错误。

## 失败证据

- 运行 `20261019-device-test-full-r1`，目录 `.tmp/appium-ios/runs/20261019-device-test-full-r1/`，无临时 URL。
- 两条均在 `03-open-ready-home-note-*` 失败，依次尝试四个 ordinal 全部 `card did not open`。
- 首条截图 `allure-results/6c3dc074-0f7f-42e1-bcdc-c0d6f41087ad-attachment.png`，XML `183ea451-25d7-4ea8-9ed8-c8915af3369c-attachment.xml`；第二条 XML `d98167a0-1370-48da-9dbe-3dcb1be11fa1-attachment.xml`。
- 实际为正常首页，有 `post-home-feed-note-card-*` 的 `XCUIElementTypeButton` 卡片；旧定位只搜索 `XCUIElementTypeOther`，候选为空。

## 第 1 轮：分析、修改与验证

- `note_card_picker.py` 优先解析可见稳定 card ID，兼容合并 Button、继承祖先隐藏状态，按屏幕顺序定位；无稳定 ID 时保留旧层级回退。
- 保留卡片几何约束和详情打开后就绪验证，不把任意首页元素当作笔记。
- 新增短标题 Button、隐藏祖先、顺序选择回归；与分享/系统通知合并验证 231 passed / 5 deselected（29.26 秒），排除项及 HEAD 基线见[分享记录](2026-10-19-share-sheet-visibility.md)。原失败 XML 修复后可读取前六个真实卡片区域。
- 真机：当前 suite 未完成，不创建第二会话；两条原用例本轮尚未执行评论/点赞/收藏操作。
- 实际清理：此两条原失败运行未新增互动数据。
- 无失败代码尝试；后续需真机验证卡片点击与完整互动断言。

## 遗留项与交接

- 当前 suite 完成后复跑两条用例，检查真实详情及互动结果。
