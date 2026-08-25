# iOS 发布笔记自动化框架优化设计

**日期：** 2026-08-22  
**范围：** iOS 真机与 iOS 模拟器  
**试点流程：** 发布笔记  
**约束：** 本轮不修改 App 代码；另行提供 `accessibilityIdentifier` 建议清单

## 背景与目标

当前 Appium + pytest 框架已经具备 iOS/Android 共用的基础动作、显式等待、session 复用、suite/profile 运行和失败产物收集能力。发布笔记流程仍有以下问题：

1. 页面控件的候选定位分散在业务模块中，页面层级或文案稍有变化就可能失效。
2. 多个候选控件会逐个消耗完整超时，固定 `sleep` 与重复首页 session 准备进一步放大耗时。
3. 定位失败时缺少统一的候选尝试记录和页面状态诊断，真机与模拟器问题不易区分。

本轮目标是建立可复用的稳定定位/等待层，并以 iOS 发布笔记为试点降低无效等待和重复操作。成功标准不是绑定某一台设备的绝对秒数，而是：

- 同一逻辑控件的定位顺序和等待行为统一、可测试、可诊断。
- 不存在的可选控件不会叠加完整超时。
- 发布笔记流程不重复准备已经就绪的首页 session。
- 真机和模拟器都能在成功或明确失败状态收敛，失败产物能指向具体阶段。
- 现有非发布笔记用例的默认行为保持兼容。

## 非目标

- 不修改 App 的 React Native/Taro 代码或页面结构。
- 不在第一版引入 OCR、图像识别或视觉相似度定位。
- 不重写已有业务流程，不改变发布笔记测试数据和断言语义。
- 不把 Android 行为扩展作为本轮交付内容；公共定位 API 保持可跨平台扩展，但本轮验证只覆盖 iOS。
- 不实现真机操作录制和脚本生成；该需求留到后续独立阶段。

## 方案概览

采用“统一定位/等待门面 + 发布笔记热路径优化”的方案。

页面模块继续暴露业务语义函数，例如 `open_message_note_publisher()`、`fill_message_note_form()` 和 `submit_message_note()`；定位细节由 `actions.py` 提供的候选定位 API 处理。每个逻辑控件声明有序候选，统一层在同一轮询周期内尝试全部候选，避免候选逐个消耗完整等待时间。

定位优先级为：

1. iOS `accessibility id`；
2. 已知页面语义文本；
3. iOS predicate；
4. 页面模块明确登记的少量 XPath；
5. 固定系统/页面按钮的坐标兜底。

第一版不缓存元素对象，避免页面刷新或转场后产生 stale element。后续如果阶段耗时数据证明有收益，再评估只缓存“上次成功的策略”，不缓存 WebElement 实例。

## 详细设计

### 1. 统一定位与等待 API

在 `apps/velowind-app/appium/velowind_appium/actions.py` 增加以下概念：

- `LocatorCandidate`：描述一个候选定位器的类型和值，可附带可读标签。
- 构造函数：`accessibility_id(...)`、`text(...)`、`ios_predicate(...)`、`xpath(...)`。
- `find_first(driver, candidates, logical_name=...)`：按声明顺序立即查找第一个可用元素。
- `wait_for_first(driver, candidates, timeout=..., required=True, logical_name=...)`：在单个截止时间内轮询候选集合。
- `tap_first(...)`：等待并点击第一个候选。
- `LocatorTimeoutError`：携带逻辑控件名、候选描述、已尝试策略、等待耗时和页面摘要。

行为约定：

- 一个轮询周期内依次尝试所有候选；任一候选成功即返回。
- `required=True` 超时抛出诊断异常；`required=False` 返回 `None`/`False`。
- 可选控件使用短默认超时，适合启动协议、提示和兼容版本按钮。
- 捕获 `NoSuchElementException`、`StaleElementReferenceException` 和普通 `WebDriverException` 后继续尝试其他候选；会话失效等不可恢复错误保留原异常上下文。
- 页面摘要只提取有限的可读文本和关键 id，避免把完整 XML 放入异常；完整 XML 仍由现有 artifact 机制保存。
- 现有 `tap_if_present`、`tap_text_if_present` 等 API 保留兼容，并逐步委托到新门面。

### 2. 发布笔记热路径

发布笔记试点调整以下模块：

- `modules/message_detail.py`：发布入口、发布类型、表单字段、图片入口、地点入口、允许评论和提交按钮迁移到候选定位 API；状态等待使用表单可见、成功信号和错误信号，而不是固定等待驱动。
- `tests/shared_publish_note.py`：发布用例复用 autouse fixture 已准备好的首页 session，不再无条件重复调用完整发布入口准备流程。
- `session.py`/`tests/conftest.py`：补充“已在首页则快速返回”的发布前准备判定；不改变需要恢复首页的其他 marker 行为。

热路径的等待策略：

- 页面和表单是必需状态，使用阶段截止时间。
- 协议弹窗、系统提示和版本兼容按钮是可选状态，使用短超时。
- 图片选择保留现有相册、裁剪和坐标兜底，但先尝试可见的 accessibility id/语义文本，避免无条件扫描多组 XPath。
- 提交后先轮询成功/失败信号；只有表单仍可见且尚未重试时才补点一次提交。
- `VW_APPIUM_PROFILE=1` 时输出 session、打开发布器、选择图片、填写表单、提交和结果校验阶段耗时；默认关闭。
- `VW_APPIUM_CAPTURE_EACH_STEP` 默认关闭，失败时沿用现有截图/XML 产物；只有显式开启才逐步采集。

### 3. 失败诊断

统一定位失败至少包含：

- 逻辑控件名；
- 候选定位类型和值；
- 实际尝试顺序；
- 总等待耗时；
- 当前页面摘要；
- artifact 目录提示（如果调用方已配置）。

业务模块在阶段失败时保留原有业务错误文案，并将定位异常作为原因链抛出，便于区分：控件未找到、页面未就绪、业务返回错误、系统相册/WDA 阻塞。

### 4. 建议 App 后续补充的 accessibilityIdentifier

本轮不修改 App，但交付以下建议清单供开发侧补充：

| 流程位置 | 建议 identifier |
| --- | --- |
| 首页底部发布入口 | `bottom-nav-publish` |
| 发布类型面板 | `publish-type-note` |
| 图片入口 | `note-media-add` |
| 相册确认/完成 | `photo-picker-done` |
| 标题输入框 | `note-title-input` |
| 正文输入框 | `note-body-input` |
| 话题入口 | `note-topic-entry` |
| 地点入口 | `note-location-entry` |
| 允许评论开关 | `note-allow-comments-toggle` |
| 提交审核按钮 | `note-submit-button` |
| 发布成功页 | `note-publish-success` |

建议 identifier 一旦发布后保持稳定，不随中文文案或视觉层级调整而改变；同一页面的输入框、按钮和状态容器应避免复用同一个 identifier。

## 文件边界

计划修改或新增：

- `apps/velowind-app/appium/velowind_appium/actions.py`：候选定位、统一等待、诊断异常。
- `apps/velowind-app/appium/velowind_appium/modules/message_detail.py`：发布笔记热路径接入统一 API。
- `apps/velowind-app/appium/velowind_appium/session.py`：发布前首页快速判定。
- `apps/velowind-app/appium/tests/conftest.py`：session 复用与耗时上下文，不改变默认 fixture 范围。
- `apps/velowind-app/appium/tests/shared_publish_note.py`：发布笔记用例去除重复准备。
- `apps/velowind-app/appium/tests/unit-test/test_actions.py`：定位层单元测试。
- `apps/velowind-app/appium/tests/unit-test/test_message_detail_helpers.py` 与 `test_session_setup.py`：发布路径回归测试。
- `apps/velowind-app/appium/test-suites/ios-p1.yaml`：独立发布笔记试点 suite（如现有 suite 结构允许则只增加引用，不复制业务用例）。
- `docs/superpowers/specs/2026-08-22-ios-publish-note-framework-optimization-design.md`：本设计文档。
- `docs/superpowers/specs/ios-accessibility-identifier-recommendations.md`：供 App 开发侧使用的标识清单。

不修改：App 源码、现有测试数据、Android 流程和与本试点无关的业务模块。

## 测试与验证

### 单元测试

- 候选按优先级返回第一个可用元素。
- 同一轮询周期会尝试全部候选，而不是对每个候选单独等待完整 timeout。
- 必需控件超时抛出包含逻辑名、候选和页面摘要的异常。
- 可选控件超时返回非异常结果。
- stale element 或瞬时 WebDriver 异常会继续尝试后续候选。
- 现有 `tap_if_present`、`tap_text_if_present` 行为保持兼容。

### 回归测试

- 现有 `test_message_detail_helpers.py`、`test_session_setup.py` 全量通过。
- 发布笔记图片选择、标题/正文填写、地点、评论开关、提交成功/失败信号相关测试全量通过。
- 现有 pytest 收集结果不减少，非发布笔记用例不改变默认 session 行为。

### 设备验证

分别在 iOS 模拟器和 iOS 真机运行发布笔记试点 suite，记录：

- driver/session 创建耗时；
- 发布入口和表单就绪耗时；
- 图片选择耗时；
- 填表耗时；
- 提交到成功信号耗时；
- 总耗时与失败阶段。

如果真机因 WDA、RemoteXPC、设备离线或签名失败无法建立 session，记录为环境阻塞，不将其归因于发布笔记代码；模拟器验证仍可独立完成。

## 风险与回滚

- 旧页面只有文本或 XPath 而没有稳定 id：保留模块级兜底，统一层不会删除已有策略。
- 新等待层改变异常类型：旧 API 继续保留，业务模块迁移按小步提交，回归测试锁定兼容行为。
- 减少固定等待后遇到慢页面：使用阶段截止时间和状态轮询，不把所有等待一刀切缩短；可通过环境变量调整默认轮询/超时。
- 首页 session 误判：沿用现有 blocker 文本和页面标识，只有确认首页状态才快速返回；失败时回退完整准备流程。

每个逻辑阶段独立提交，若设备验证发现回归，可只回滚对应模块迁移，不影响新定位 API 和诊断能力。

