# 测试用例修复记录

这里记录每次测试修复的分析和验证过程，供后续修复前检索。2026-09-14 至 2026-09-15 的首批记录根据本次会话、当前代码和本地 Allure 结果补录；无法重新核实的细节明确注明，不补造过程。

## 按问题查找

| 问题 / 检索词 | 记录 | 已确认范围 |
| --- | --- | --- |
| iOS 拍摄视频、使用视频、Playback / Done、recording could not be completed | [系统视频确认](2026-11-06-ios-camera-native-video-confirm.md) | 已补两级预览确认，96单元通过；真机setup因设备离线失败，完整流程与清理待验证 |
| 图片比对、pixel-delta-too-high、大图黑边、全屏 Image bounds | [大图内容区域](2026-11-06-ios-image-viewer-content-bounds.md) | 目标真机1 passed且新增笔记API删除成功；245单元通过、5项历史mock失败，原失败笔记未清理 |
| 发布后详情打不开、post-detail-title、我的笔记新版 Tab | [详情标题标识误读](2026-11-06-ios-published-detail-title-id.md) | 已修正，22项定向单元通过；真机原笔记打开与标题核验通过；全文件232通过5项mock失败，完整发布未重跑、原笔记未清理 |
| Appium 已启动、Connection refused、4723 / 4725 | [Appium 服务端口不一致](2026-11-06-appium-server-port.md) | 已确认脚本连4723、服务监听4725；4725就绪及环境变量覆盖已验证，完整真机未重跑 |
| Android 选错图片、影集长白山、强制相机第一张 | [按指定影集选图](2026-11-05-android-requested-photo-album.md) | 真机1 failed未发布；已从本机DEX与日志确认固定本地分类、扩展相册源关闭，不展示长白山；替代入口待适配 |
| 测试优惠券、900/1800清理、扫码动态发码、库存预留 | [测试券清理与扫码发码](2026-10-30-test-coupon-cleanup.md) | 两旧模板及关联记录已软删除；新900扫码模板20张、预生成0，实际扫码未验证 |
| Android 环境识别、Me or login page、个人页子节点、设置 bounds、协议、键盘 | [Android 环境登录准备](2026-10-27-android-environment-login.md) | 登录准备真机已通过；235项联合单元通过，视频漏扫修复待设备重新连接后完整复验 |
| 账号识别环境、App 多环境登录、匹配清理账号 | [App 登录识别环境](2026-10-27-app-environment-login.md) | 已按用户流程移除跨环境 API 核验；218项关联单元通过，原场次真机1 passed且未清理；本轮未重跑笔记删除、P1整套 |
| 发布成功、清理 400、17210004、post.not_found | [API 清理目标不存在](2026-10-27-note-cleanup-post-not-found.md) | 独立生产配置下完整目标 1 passed，新笔记 prod-api 实际删除成功；旧 ID 在生产查询不存在，未称本轮删除 |
| iOS 发布入口、bottom-nav-center-action、点击无跳转 | [发布入口有限重试](2026-10-27-ios-publish-entry-transition.md) | 307 项消息/相册单元通过；生产真机完整目标 1 passed，新笔记实际删除成功 |
| 全消息自动化、CSV MSG-001—032、已读图标、最新消息定位、Allure | [消息脚本接入](2026-10-19-message-regression.md) | 私信本轮13子检查：11通过2失败；已读仍为已发送，旧历史漂移27px；连续来信底部跟随通过；原13项均已补描述及PNG；新报告15项11通过4失败，混合发送受频控阻断；58项离线通过，全量未完成 |
| 私信图片、sendEntry、发送结果查询400、频控 | [私信图片发送结果](2026-10-20-private-image-send-entry.md) | 必填参数已补；原图SENT已找回未重发；混合序列仍频控失败，未完成显示验证 |
| 模拟支付、Postman mock callback、测试订单 paymentOrderId | [模拟支付回调](2026-10-19-payment-mock-callback.md) | 独立工具26项离线通过；实际回调、报名适配及真机未验证 |
| 租车门店、上海徐汇店、虹桥店、无法选择首个门店 | [实际门店数据](2026-10-19-rental-store-data.md) | 26 单元通过；实际选项名称兼容，完整真机复验中 |
| 活动分类、全部活动更名全部 | [活动分类文案](2026-10-19-activity-category-label.md) | 已补新旧文案兼容，真机复验待执行 |
| 活动搜索、张家界无结果、测试数据关键词 | [活动搜索数据](2026-10-19-activity-search-data.md) | 已配置现有地点及关键词覆盖；真机复验待执行 |
| 活动卡片缺失、快照第 50 层、报名用例误跳过 | [iOS 快照深度](2026-10-19-ios-snapshot-depth.md) | 80 真机失败已保留；60 深度现场可读取 6 张卡片，统一配置复验待执行 |
| 活动行程、新增第二段、31×30 加号 | [行程控件取整](2026-10-19-activity-itinerary-add-control.md) | 现场确认尺寸差异，已补 1 像素容差；真机复验待执行 |
| 系统通知、系统消息入口等待超时 | [系统通知文案](2026-10-19-system-notification-entry.md) | 新版文案兼容已补，真机复验待执行 |
| 首页 ordinal、card did not open、Button 卡片 | [首页 Button 卡片](2026-10-19-home-note-button-cards.md) | 稳定 card ID 兼容已补，真机复验待执行 |
| 朋友圈、分享后已回详情、汇总文字误判面板 | [分享面板可见性](2026-10-19-share-sheet-visibility.md) | 相关合并单元通过；真机完整交互用例 7 步 passed，互动数据未清理 |
| 草稿、Unable to enter the Me page、详情误点留言 | [草稿导航恢复](2026-10-19-draft-me-navigation.md) | 8 单元通过；真机完整用例 6 步 passed，草稿清理未执行 |
| 真机 1.3.0、摄像头图标偏移、视频候选为 0 | [摄像头搜索范围](2026-10-19-home-video-camera-position.md) | 47 单元通过；测试环境真机目标 passed，两个视频播放通过，整套运行中 |
| VW_API_ENV=test、dev-api、测试环境 Host | [测试环境 API 映射](2026-10-19-test-api-environment.md) | 41 单元通过；测试真机图片发布通过，dev-api 登录与删除成功，无笔记清理遗留；整套运行中 |
| 登录准备失败、Login page remained visible、setup 无附件、测试环境 | [登录准备失败](2026-10-19-login-session.md) | 133 单元通过；已切用户更新的 dev-api 真机，原视频目标通过，整套回归中；保留各轮原失败 |
| iOS 短标题、相同正文、地点误作标题、测试 / 测试 | [短笔记内容误读](2026-10-10-ios-short-note-content.md) | 240 单元通过，5 条既有发布 mock 排除；原用例完整真机 1 passed（7 步），互动数据未清理 |
| 租车订单取消、释放车辆、自动清理 | [租车自动取消](2026-09-30-rental-order-cleanup.md) | 32 单元通过；目标真机 1 passed、实际取消成功，本次无订单遗留 |
| Android 租车订单、旧详情混入、剩余支付时间缺失 | [订单卡片误读](2026-09-30-android-rental-order-card.md) | 25 单元通过；目标真机 1 passed；后续自动清理见上一条 |
| 执行效率、场次日期、滚轮读取 | [iOS 效率优化](2026-09-21-ios-efficiency.md) | 152 单元通过；候选真机两轮通过，场次节省 10.5%–12.1%；整套未复跑、场次未清理 |
| iOS 浏览笔记、详情加载失败、错误页被识别为详情 | [详情加载失败](2026-09-21-ios-note-detail-load-failure.md) | 232 单元通过，5 条既有失败单独记录；完整目标用例真机 1 passed，互动数据未清理 |
| Android 拍摄视频、相机权限、仅在使用中允许 | [相机授权阻塞](2026-09-20-android-camera-permission.md) | 已补系统媒体授权处理；单元 84 passed，真机 1 passed 且新增笔记删除成功 |
| 发布后删除、登录 HTTP 400、Incorrect password、UAT 清理 host | [API 清理环境配置](2026-09-20-note-cleanup-login-password.md) | 历史生产真机 1 passed 且删除成功；2026-09-30 按当前 UAT App 固定清理 host，UAT 真机清理待验证 |
| 首页视频数量、2 个视频、VW_HOME_VIDEO_COUNT | [视频检查数量可配置](2026-09-20-home-video-count.md) | 默认检查 2 个；单元 43 passed；真机未验证 |
| 私聊接收侧、clientMessageId mismatch | [接收视角断言](2026-09-18-api-private-chat-recipient-client-id.md) | 已修复，真实B四条/C五条接收核验通过 |
| 活动分享、17000025、provider unavailable | [活动卡片阻断](2026-09-18-api-private-chat-activity-provider.md) | 两条公开活动均失败，待后端核查 |
| 私聊API、Unread baseline mismatch、基线26 | [私聊未读基线准备](2026-09-18-api-private-chat-unread-baseline.md) | 基线与发送节奏实测通过；整套活动分享仍阻断 |
| Android 朋友圈分享、Unable to confirm the Moments share | [微信登录前置条件](2026-09-16-android-moments-login.md) | 原报告确认停在微信登录页；登录后复测未执行 |
| 图片发布、相册权限、无可选照片 | [权限说明误判为相册](2026-09-16-ios-photo-permission-picker.md) | 已修复误判；用户授权后真机 1 passed、实际删除成功；单元 278 passed |
| iOS 模拟器首页 0/4、卡片 ID 缺失 | [模拟器视频筛选分析](2026-09-16-ios-simulator-video-discovery.md) | 模拟器 1.2.4 与真机 1.2.6 不同；补逐屏诊断，真机四视频 1 passed；旧模拟器未修复 |
| Android 首页 0/4、0/2、1/2 视频、滑动漏扫 | [Android 视频候选不足](2026-09-15-android-video-candidates.md) | 10月27日1/2复发已补受控滚动，探针发现2个候选、235联合单元通过；设备离线，完整播放待复验；历史通过保留 |
| Android 初始化、WRITE_SECURE_SETTINGS、hidden_api_policy | [Android 隐藏 API 兼容](2026-09-15-android-hidden-api.md) | 显式兼容开关解除建会话阻塞；17 项单元通过；完整用例因 0/4 视频失败 |
| 固定日期、场次结束日期断言 | [活动场次日期断言](2026-09-15-activity-session-date-assertion.md) | 已修正；目标真机用例 1 passed |
| 活动场次、管理场次超时、通过但未发布、最后滚动后目标出现 | [活动场次入口边界](2026-09-15-ios-activity-session.md) | 10月27日已兼容通过+未发布；218项关联单元通过，原完整真机目标1 passed；新场次未删除，整套未复跑 |
| 首页四个视频、摄像头图标、照片误选、播放错误误判 | [首页视频筛选与 iOS P1](2026-09-14-ios-p1.md#首页四个视频的筛选与播放校验) | 历史整套运行 14 passed；不包含清理完成结论 |
| 卡片合并标签、长标题、异步上传、重复视频标题 | [发布成功信号与目标卡片定位](2026-09-14-ios-p1.md#发布成功信号与目标卡片定位) | 当时发布用例通过；后续误入详情问题见下一条 |
| `Unable to locate the published note detail image`、图片用例进入视频 | [详情误选的连续修复](2026-09-15-ios-publish-cleanup.md#问题一图片用例误入视频详情) | 20260915-101707-55481 三个发布用例通过 |
| 标题换行、标题截断、不自动删除、`cleanup-pending` | [自动清理与实际标题](2026-09-15-ios-publish-cleanup.md#问题二标题换行截断与自动清理) | 新一轮图片、相册视频删除成功；其他范围需查后续报告 |
| 视频第 4 帧、`loading or blank`、正在缓冲视频 | [实际缓冲失败](2026-09-15-ios-publish-cleanup.md#问题三视频采样时实际缓冲) | 保留失败；后一轮视频内容校验通过 |
| walkthrough、租赁页、失败步骤被吞掉 | [功能遍历的真实结果](2026-09-14-ios-p1.md#功能遍历不能吞掉失败步骤) | 历史整套运行 14 passed，65 个步骤无失败 |
| `InvalidSessionIdException`、真机会话被替换 | [真机会话冲突](2026-09-15-ios-publish-cleanup.md#问题四独立验证与整套测试竞争会话) | 确认出现会话失效，独立验证不算完成 |

## 使用方式

1. 先按用例名、报错或模块搜索本目录，阅读对应记录中的无效尝试和适用条件。
2. 获取当前报告的失败步骤、截图和 XML，先确认打开了哪个页面、哪篇笔记，再分析媒体状态或清理结果。
3. 使用 [模板](TEMPLATE.md) 建立 `YYYY-MM-DD-问题简述.md`。同一问题复发时追加尝试，注明复发报告，不覆盖旧结论。
4. 每轮记录实际运行结果，结束时更新本索引的状态和遗留项。

```bash
rg -n 'test_four_home_videos_play_normally|cleanup-pending|detail image|换行' apps/velowind-app/appium/docs/test-fixes
```

## 证据与结果口径

- 报告同时记录运行目录和当时的 HTTP 地址。localhost 端口是临时入口，服务关闭后应从 `.tmp/appium-ios/runs/<run-id>/allure-results/` 或 `allure-report/` 读取证据。
- `.tmp` 文件可能被清理；关键报错、观察和结果必须在 Markdown 中保留。需要长期保留的截图应单独归档并脱敏，不复制整份测试报告或认证信息进 Git。
- `publish-note-cleanup-result` 记录删除结果；`publish-note-cleanup-pending` 表示仍有遗留。pytest 显示通过时也要检查这两类附件。
- “待验证”“现场验证失败”“局部通过”“整套通过”和“清理成功”分别记录。不要用一次成功掩盖先前复发或未完成验证。
