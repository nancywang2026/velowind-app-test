# 寻风集 App 真机探索测试与 Bug 报告

## 1. 测试结论

本轮确认了 **2 个产品缺陷、3 个测试/交付基础设施缺陷、1 个测试环境阻塞风险**。

- 产品缺陷中，首页运动分类语义错误可稳定复现；笔记搜索长时间停留在加载态为偶发问题。
- iOS 登录、首页、活动、消息、我的主导航均可达；活动“骑行”分类筛选通过。
- 租车入口本身可以正常进入，但现有 smoke 脚本会把内部等待失败吞掉并最终报 PASS，存在假绿。
- Android 模拟器曾被另一条自动化会话同时控制，导致导航用例受到串扰；相关失败不计为产品 Bug。
- 用户指定的前后端源码与真机安装包不匹配，无法用指定仓库对当前安装包做严格源码追溯。

## 2. 测试环境

| 项目 | 环境 |
| --- | --- |
| iOS 真机 | Zhigang的iPhone，iPhone 17，iOS 26.2.1 |
| iOS App | 寻风集 1.2.0，build 24，Bundle ID `com.velowind.rider` |
| Android | API 35 arm64 模拟器，`emulator-5554` |
| Android App | 寻风集 1.2.1，versionCode 17，Package `com.velowind.rider` |
| 登录账号 | `133****9990`，密码登录成功 |
| 指定前端仓库 | `/Users/test/github/velowind-app`，`main@b3541cdd`，版本 1.1.2 |
| 指定后端仓库 | `/Users/test/github/velowind-backend-service`，`main@87d2e77c` |
| 实际匹配 iOS 1.2.0 的本机源码 | `/Users/test/Documents/velowind-app-dev`，`dev@d0e1d9eb` |
| 自动化 | Appium 3.5.2、XCUITest、UiAutomator2、pytest、Allure |
| 测试日期 | 2026-07-15，Asia/Shanghai |

## 3. 执行结果

| 场景 | 平台 | 结果 | 说明 |
| --- | --- | --- | --- |
| 登录并进入首页 | iOS 真机 | 通过 | 使用指定账号密码 |
| 首页、活动、消息、我的主导航 | iOS 真机 | 通过 | 连续执行 2 次 smoke |
| 首页租车入口 | iOS 真机 | 产品通过 / 脚本异常 | 页面进入成功，自动化等待步骤 `broken` 后被吞掉 |
| 搜索“骑行”并打开笔记 | iOS 真机 | 1 失败、1 通过 | 首次停留加载态，复跑通过 |
| 首页按“骑行”筛选笔记 | iOS 真机 | 失败 | 返回非骑行标签内容 |
| 活动按“骑行”筛选 | iOS 真机 | 通过 | 可见活动卡均为骑行 |
| 首页骑行、徒步、滑雪分类可达 | Android | 通过 | 公共页面巡检 |
| Android 底部导航 | Android | 结果无效 | 同设备存在并发自动化会话，发生页面串扰 |

## 4. 产品缺陷

### BUG-001：首页运动分类实际使用全文搜索，分类结果失真

- 严重程度：高
- 复现率：稳定复现
- 影响范围：首页“骑行、徒步、滑雪、登山”等分类 Tab

复现步骤：

1. 登录后进入首页。
2. 点击顶部“骑行”。
3. 查看首屏笔记卡片的标签和正文归类。

期望结果：

- “骑行”分类只展示明确归类为骑行的内容。
- 卡片可见主题标签应与当前分类一致。

实际结果：

- 当前分类高亮为“骑行”，但首屏出现标签为 `#云南洱海` 的笔记。
- 生产接口直接查询表明，该笔记只是正文中出现“徒步与骑行”，因此被全文搜索命中。

证据：

- [失败截图：骑行分类出现云南洱海笔记](/Users/test/Documents/velowind-app-dev-test/.tmp/appium-ios/20260715-223753-test_user_can_filter_notes_by_type.png)
- 生产接口 `/api/v1/mobile/posts/search?keyword=骑行&pageNo=1&pageSize=20` 返回该洱海内容。
- [分类将“骑行”映射为 queryCode](/Users/test/Documents/velowind-app-dev/packages/post/src/page/home-feed/homeFeedCategories.ts:31)
- [首页分类实际调用全文搜索 keyword](/Users/test/Documents/velowind-app-dev/packages/post/src/services/postHomeFeedService.ts:112)

根因判断：

- 前端把业务分类 Tab 实现为 `topic-search`，再调用全文搜索接口并传 `keyword=骑行`。
- 全文搜索会匹配标题、正文或 topics，而不是验证内容的 canonical 运动类型，因此 UI 的“分类”语义与接口的“搜索”语义不一致。

建议：

- 为 Post 增加独立的运动类型/分类字段，并通过枚举值过滤，例如 `CYCLING`、`HIKING`、`SKIING`。
- 分类 Tab 不再复用全文搜索；若仍需全文搜索，应把 UI 文案明确改成“含骑行内容”。
- 增加接口契约测试：返回 items 的分类字段必须全部等于请求分类。

### BUG-002：笔记搜索偶发长时间停留“正在加载”，没有超时或重试出口

- 严重程度：高
- 复现率：本轮 1/2；历史用例存在通过记录，属于偶发
- 影响范围：笔记搜索页、其他复用同一 API Client 的页面

复现步骤：

1. 登录后进入首页。
2. 点击搜索图标。
3. 输入“骑行”并提交。
4. 等待 12 秒以上。

期望结果：

- 正常网络下数秒内展示结果。
- 请求超时或失败时展示错误态，并提供重试。

实际结果：

- 页面持续显示“正在加载真实搜索结果”，超过 12 秒仍未收敛为成功、空结果或错误。
- 同一场景随后复跑通过，说明不是固定无数据问题。
- 生产搜索接口从测试机直接请求约 0.7 秒返回，服务端当时可用。

证据：

- [失败截图：搜索持续加载](/Users/test/Documents/velowind-app-dev-test/.tmp/appium-ios/20260715-223608-test_user_can_search_and_open_note.png)
- [失败页面树](/Users/test/Documents/velowind-app-dev-test/.tmp/appium-ios/20260715-223608-test_user_can_search_and_open_note.xml)
- [搜索组件只等待 Promise 成功或失败](/Users/test/Documents/velowind-app-dev/packages/post/src/search/PostSearchLiveResults.tsx:71)
- [Axios 实例未配置 timeout](/Users/test/Documents/velowind-app-dev/packages/foundation/src/api/createAxiosApiClient.ts:430)

根因判断：

- 已确认现象是请求发起后 UI 一直处于 loading。
- 高可信推断：客户端没有请求超时，页面也没有独立的超时状态；网络请求一旦悬挂，Promise 不 resolve/reject，页面即可无限加载。
- 本次失败对应的 requestId 未能从真机持久日志中提取，因此不能断言具体悬挂发生在 DNS、TLS、Axios、鉴权刷新或服务端链路。

建议：

- 通用 API Client 设置明确超时，并区分连接超时、响应超时与取消。
- 搜索页面增加超时错误态、重试按钮和离开页面时的请求取消。
- 在自动化失败附件中输出对应 requestId、fullUrl、duration 和最终 result。

## 5. 测试与交付基础设施缺陷

### TEST-001：iOS smoke 吞掉租车入口等待失败，最终形成假绿

- 严重程度：高
- 复现率：2/2

现象：

- Appium 截图确认租车页已经进入并可正常显示。
- `wait-entry-floating-rental-mode-entry-car` 连续两次在 10 秒后标为 `broken`。
- 外层捕获 `WebDriverException` 后仅执行返回操作，pytest 最终仍为 `1 passed`。

证据：

- [租车页已进入](/Users/test/Documents/velowind-app-dev-test/.tmp/appium-ios/20260715-230759-test_ios_feature_walkthrough-12-tap-entry-floating-rental-mode-entry-car.png)
- [等待失败时截图](/Users/test/Documents/velowind-app-dev-test/.tmp/appium-ios/20260715-230814-test_ios_feature_walkthrough-13-wait-entry-floating-rental-mode-entry-car.png)
- [脚本捕获并吞掉异常](/Users/test/Documents/velowind-app-dev-test/apps/velowind-app/appium/tests/smoke/test_ios_feature_walkthrough.py:66)

建议：

- 让租车页面稳定暴露 `rent-page-shell` 可访问性 ID，并在真机页面树中验证。
- smoke 不应吞掉关键入口断言；恢复现场后仍应让用例失败。
- pytest 结果与 Allure 步骤状态必须一致，禁止顶层 PASS 内含关键 `broken` 步骤。

### TEST-002：真机安装包与用户指定源码仓库不一致

- 严重程度：高
- 类型：可追溯性/提测配置缺陷

现象：

- 指定前端仓库版本为 1.1.2，iOS 安装包为 1.2.0，Android 安装包为 1.2.1。
- 指定前端仓库没有当前真机正在使用的 `packages/post` 首页笔记实现。
- 指定后端仓库也没有当前安装包请求的 `/api/v1/mobile/posts/search` 合约。
- 本机另一份 `/Users/test/Documents/velowind-app-dev` 才与 iOS 1.2.0 功能和文案一致。

影响：

- 无法从用户指定仓库严格定位当前安装包缺陷。
- 修复可能落到错误分支，回归也无法证明修复进入了受测包。

建议：

- App“关于/调试信息”中展示 version、build number、Git SHA、环境名和 API Base URL。
- 每个测试包附带不可变 build manifest，并由报告自动采集。
- 提测时锁定前端 SHA、后端 SHA、配置环境和安装包哈希。

### TEST-003：Android 同一设备允许并发 Appium 会话，结果和附件互相污染

- 严重程度：高
- 复现率：本轮连续两组 Android 导航测试均受到串扰

现象：

- 本轮底部导航测试运行时，产物目录同时出现另一条 `test_user_can_search_and_open_note` 的截图和结果。
- 两条测试使用不同 Appium session，但同时操作 `emulator-5554`。
- 导航测试等待“活动”时，失败截图实际停留在首页“滑雪”分类；随后又被切到搜索页。
- 后启动的测试清理共享 Allure 目录，导致前一轮结果文件消失。

代码风险：

- [Android session fixture 没有基于 UDID 的互斥锁](/Users/test/Documents/velowind-app-dev-test/apps/velowind-app/appium/tests/android_smoke/conftest.py:16)
- 所有运行共用 `.tmp/appium-android/allure-results` 和同一截图目录。

建议：

- 创建基于 `platform + UDID` 的进程锁；设备被占用时 fail fast。
- 每轮使用唯一 `runId` 的 artifact/allure 目录，结束后再聚合。
- 报告记录 sessionId、UDID、PID、启动时间，检测重叠会话并将结果标记为无效。

## 6. 测试环境风险

### ENV-001：`test-api.velowind.com` TLS 证书已过期

- 严重程度：阻塞测试环境
- 证书有效期：2026-03-30 至 2026-06-28
- 检查日期：2026-07-15
- 严格 TLS 请求结果：curl error 60，`ssl_verify_result=10`，HTTP 000

实际 1.2.0 真机数据来自生产环境，本轮产品缺陷并非由该过期证书导致；但任何指向 `.env.test` 的新测试包都会无法正常访问 API。

建议立即续签证书，并增加证书到期前 30/14/7 天告警。

## 7. 未计入产品 Bug 的异常

- Android “活动、消息、我的”导航失败：已确认存在并发会话操作同一模拟器，结果无效。
- iOS 租车入口等待失败：截图确认产品页面已进入，属于自动化可访问性/断言问题。
- 首页相似内容重复：当前数据中存在多条标题和图片高度相似的自动化发布内容，暂按测试数据污染处理，未证明是客户端重复渲染。

## 8. 建议修复顺序

1. 先解决源码/安装包可追溯性与设备并发锁，否则后续定位和回归结果不可信。
2. 修复首页分类接口语义，使用独立 canonical 分类字段。
3. 为 API Client 和搜索页补齐超时、取消、错误与重试状态。
4. 修复 iOS smoke 假绿，让关键步骤失败能正确传递到 pytest。
5. 续签测试环境 TLS 证书并接入到期监控。

