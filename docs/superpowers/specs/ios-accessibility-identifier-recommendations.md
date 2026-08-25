# 发布笔记流程 accessibilityIdentifier 建议

这份清单供 App 开发侧后续补充，不属于本轮测试框架改动。identifier 一旦发布后应保持稳定，不随中文文案、层级或视觉样式调整而改变。

| 流程位置 | 建议 identifier | 说明 |
| --- | --- | --- |
| 首页底部发布入口 | `bottom-nav-publish` | 打开发布类型面板 |
| 发布类型面板中的笔记 | `publish-type-note` | 进入图文笔记编辑页 |
| 笔记编辑页图片入口 | `note-media-add` | 打开系统相册/媒体选择器 |
| 相册选择完成 | `photo-picker-done` | 确认已选图片并返回编辑页 |
| 标题输入框 | `note-title-input` | 独立于 placeholder 和中文标题 |
| 正文输入框 | `note-body-input` | 独立于 placeholder 和中文正文 |
| 话题入口 | `note-topic-entry` | 打开话题选择或输入区域 |
| 地点入口 | `note-location-entry` | 打开地点搜索/选择页 |
| 允许评论开关 | `note-allow-comments-toggle` | 对应当前笔记的评论设置 |
| 提交审核按钮 | `note-submit-button` | 提交发布笔记 |
| 发布成功页容器 | `note-publish-success` | 表示成功/待审核状态已出现 |

实现建议：输入框、按钮、状态容器各自使用唯一 identifier；不要把同一 identifier 同时赋给父容器和可点击子元素；系统相册控件只在 App 自有可控入口上补充标识，系统页面本身不做改动。
