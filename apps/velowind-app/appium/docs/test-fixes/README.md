# 测试用例修复记录

这里记录每次测试修复的分析和验证过程，供后续修复前检索。2026-09-14 至 2026-09-15 的首批记录根据本次会话、当前代码和本地 Allure 结果补录；无法重新核实的细节明确注明，不补造过程。

## 按问题查找

| 问题 / 检索词 | 记录 | 已确认范围 |
| --- | --- | --- |
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
| Android 首页 0/4、0/2 视频 | [Android 视频候选不足](2026-09-15-android-video-candidates.md) | 已补 Android 截图识别及密度换算；单元 46 passed，真机 1 passed、两个视频播放通过 |
| Android 初始化、WRITE_SECURE_SETTINGS、hidden_api_policy | [Android 隐藏 API 兼容](2026-09-15-android-hidden-api.md) | 显式兼容开关解除建会话阻塞；17 项单元通过；完整用例因 0/4 视频失败 |
| 固定日期、场次结束日期断言 | [活动场次日期断言](2026-09-15-activity-session-date-assertion.md) | 已修正；目标真机用例 1 passed |
| 活动场次、管理场次超时、最后滚动后目标出现 | [活动场次入口边界](2026-09-15-ios-activity-session.md) | 相关单元通过；目标真机 1 passed，入口实测 106.79 秒；场次未清理 |
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
