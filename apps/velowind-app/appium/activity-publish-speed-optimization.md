# 发布活动真机用例提速方案与进度

日期：2026-07-11  
分支：`f_refactor_speed`

## 问题背景

发布活动真机用例曾出现外层命令超过 15 分钟仍未返回 pytest 结果的情况。历史快照显示活动发布流程曾能到达 `我的活动` 列表并出现 `待审` 活动记录，因此当前优化重点不是先假设业务失败，而是降低 Appium 真机执行过程中的无效等待、重 XPath 扫描和过重测试数据带来的耗时。

## 优化策略

### 1. 降低无效候选等待成本

发布活动入口、活动类型入口、提交按钮等函数会按多个 accessibility id 和文本候选逐个查找。原先每个候选默认等待 2 秒；当候选不存在时，多个候选会叠加成明显耗时。

策略：

- 对“可选候选”使用短等待。
- 保留外层循环和页面就绪等待，让页面加载仍有机会成功。
- 避免每个不存在的候选都消耗 2 秒。

已开始改动：

- 新增 `FAST_OPTIONAL_TAP_TIMEOUT = 0.5`。
- `_tap_publish_entry_if_present()` 使用短等待。
- `_tap_activity_type_if_present()` 使用短等待。
- `_tap_form_field()`、`_tap_placeholder()`、`_choose_specific_overlay_option()`、`_choose_first_option()`、`_tap_submit()` 的候选点击使用短等待。

### 2. 减少 XPath 使用

XPath 在 iOS 真机 Appium 上通常比 accessibility id、iOS predicate、坐标点击更慢，尤其是全树搜索和 `contains()`。

策略：

- 已经有 iOS predicate 的精确文本查找时，不再重复 exact XPath。
- 对固定位置入口优先使用坐标点击，避免先跑多条坐标 XPath。
- 对确实没有稳定 accessibility id 的兜底场景，暂时保留少量 XPath。

已开始改动：

- `_tap_form_field()` 移除精确文本 XPath 兜底，优先使用 `tap_text_if_present()`，必要时使用传入坐标兜底。
- `_tap_placeholder()` 移除精确文本 XPath 兜底。
- `_tap_image_picker()` 改为优先坐标点击图片入口，再使用旧 XPath 兜底。
- `_choose_specific_overlay_option()` 移除 exact XPath，保留包含匹配兜底。
- `_fill_input_near_label()` 在执行 XPath 之前，先检查目标关键字是否出现在当前 `page_source` 中；对根本不存在的字段直接跳过，避免无效全树搜索。
- `_fill_known_text_fields()` 去掉与 `_fill_city()` 重复的 `城市名称` 二次填写，减少重复定位与输入。

### 3. 按发布类型复用相册模块，但允许不同选择策略

发布笔记与发布活动已经共享 `photo_picker.py`，但两者对“指定相册后如何选图”的需求并不完全相同：

- 发布笔记：仍保持进入指定相册后全选，覆盖多图发布主链路。
- 发布活动：只需要封面图，进入指定相册后选择首张图即可。

已完成改动：

- `photo_picker.choose_photo_from_library()` / `choose_local_photo()` 新增 `select_all_from_album` 参数，默认仍为 `true`，保证发布笔记路径不变。
- 发布活动 `_upload_activity_image()` 显式传 `select_all_from_album=False`，走轻量单图选择路径。

### 4. 控制测试数据复杂度

当前发布活动测试数据包含 3 段行程。每段行程都需要在真机上打开编辑器、定位字段、输入标题/副标题/正文，并且第二、三段还需要添加行程段。这是高耗时路径。

建议方案：

- 保留 1 段行程用于覆盖发布活动必填路径。
- 将长文本压缩为足够触发业务校验的短文本。
- 如果需要覆盖多段行程能力，单独拆成非主发布链路用例，不放在“发布活动能提交审核”的主路径里。

当前状态：

- 曾尝试将发布活动主链路测试数据从 3 段行程压缩为 1 段行程。
- 该方案真机失败，页面仍显示 `活动行程 * 点击补充活动行程安排`，说明单段行程没有被产品保存为有效活动行程。
- 下一步改为 2 段行程：比原 3 段减少一次添加和一组字段输入，同时保留多段行程结构。
- `_fill_itinerary()` 的多段行程能力仍由 helper 单测覆盖，没有删除模块能力。

### 5. 提升可观测性

15 分钟外层超时时没有 pytest 失败快照，说明命令被外部 timeout 杀掉，fixture 没机会保存最终页面。

建议方案：

- 真机调试阶段开启 `VW_APPIUM_CAPTURE_EACH_STEP=1`。
- 必要时为活动发布关键阶段加临时耗时日志：打开发布页、上传图片、填写标题、选择类型/省份、填写详情、填写行程、解析剩余 picker、提交审核。
- 验证稳定后不保留过多日志，避免污染测试输出。
- 本轮已在 `activity.py` 中加入默认关闭的 `VW_ACTIVITY_PROFILE=1` 分阶段耗时日志，便于真机定位热点而不影响常规执行。

## 已完成改动范围

已提交过的共享相册修复：

- `apps/velowind-app/appium/velowind_appium/modules/photo_picker.py`
- `apps/velowind-app/appium/velowind_appium/modules/activity.py`
- `apps/velowind-app/appium/velowind_appium/modules/message_detail.py`
- `apps/velowind-app/appium/tests/test_photo_picker_helpers.py`
- `apps/velowind-app/appium/tests/test_activity_helpers.py`
- `apps/velowind-app/appium/tests/test_message_detail_helpers.py`
- `apps/velowind-app/appium/tests/message/test_ios_publish_note.py`
- `apps/velowind-app/appium/ios-photo-picker-fix-summary.md`

本轮正在进行的提速改动：

- `apps/velowind-app/appium/velowind_appium/modules/activity.py`
  - 增加短等待常量。
  - 减少发布活动热路径中的重复 XPath。
  - 图片入口优先坐标点击。
  - 首页底部发布入口改为优先坐标点击，再走 id/text/XPath 兜底。
  - `publish_activity()` / `fill_activity_form()` 增加可开关阶段耗时日志。
  - `_fill_input_near_label()` 增加关键字预筛，避免无效 XPath。
  - `_fill_known_text_fields()` 去除重复城市填写。
- `apps/velowind-app/appium/tests/activity/testdata/publish_activity.yaml`
  - 曾将默认发布活动用例从 3 段行程压缩为 1 段行程，但真机验证失败。
  - 下一步调整为 2 段行程，兼顾保存成功率和执行速度。
- `apps/velowind-app/appium/velowind_appium/modules/photo_picker.py`
  - 在共享相册模块中支持“指定相册后全选”与“指定相册后单选首图”两种策略。
  - 默认仍保持全选，活动发布显式走单图路径。
- `apps/velowind-app/appium/tests/test_activity_helpers.py`
  - 同步默认 draft 解析期望。
- `apps/velowind-app/appium/tests/test_photo_picker_helpers.py`
  - 同步共享相册模块新参数的 helper 断言。

新增说明文档：

- `apps/velowind-app/appium/activity-publish-speed-optimization.md`

## 当前验证状态

已完成验证：

- 发布笔记 `publish-note-changbaishan` 真机用例已通过。
- photo picker、activity helper、message detail helper 曾通过 `74 passed`。
- 本轮短等待和 XPath 调整后，相关 helper 已重新通过：

```bash
PYTHONPATH=apps/velowind-app/appium python3 -m pytest \
  apps/velowind-app/appium/tests/test_activity_helpers.py \
  apps/velowind-app/appium/tests/test_photo_picker_helpers.py \
  apps/velowind-app/appium/tests/test_message_detail_helpers.py -q
```

结果：

```text
74 passed, 1 warning in 9.89s
```
- 单段行程测试数据调整后，相关 helper 再次通过：

```text
74 passed, 1 warning in 9.96s
```
- 单段行程真机验证失败：

```text
1 failed, 1 warning in 500.57s (0:08:20)
AssertionError: The activity itinerary placeholder is still visible after closing the editor
```

失败快照关键信息：

- `活动行程 * 点击补充活动行程安排` 仍可见。
- `Day1`、`集合说明`、`石家庄集合签到`、`完成签到` 均不在最终页面中。
- 结论：单段行程不适合作为当前发布活动主链路数据。
- 2 段行程调整后，相关 helper 通过：

```text
74 passed, 1 warning in 9.96s
```
- 活动和笔记真机验证后，最终相关 helper 再次通过：

```text
74 passed, 1 warning in 9.97s
```
- 2 段行程发布活动真机验证通过：

```text
1 passed, 1 warning in 771.47s (0:12:51)
```

优化效果：

- 对比原先 `0:14:55`，缩短约 `2:04`。
- 对比坐标优先后的 `0:14:35`，缩短约 `1:44`。
- 当前结果已低于 15 分钟，但整体仍偏长。后续若继续优化，应优先分析编辑器输入和 picker 字段解析耗时。

待重新验证：

- 发布活动真机用例。
- 发布笔记真机用例，确认活动侧优化没有影响共享相册模块和笔记流程。

## 真机验证记录

### 2026-07-12 发布活动复跑

当前状态：阻塞在真机 WebDriverAgent 启动阶段，未进入发布活动用例本体。

执行命令：

```bash
PYTHONPATH=apps/velowind-app/appium python3 -m pytest \
  'apps/velowind-app/appium/tests/activity/test_ios_publish_activity.py::test_user_can_publish_activity_for_review' \
  -q -m full
```

结果：

```text
ERROR at setup of test_user_can_publish_activity_for_review
selenium.common.exceptions.WebDriverException:
Unable to launch WebDriverAgent. Original error: xcodebuild failed with code 65
```

补充信息：

- 设备列表显示 `Zhigang的iPhone (26.2.1) (00008150-0006799C2693401C)` 在线。
- 连续两次复跑均在 `create_ios_driver()` 阶段失败。
- 因失败发生在 Appium session 创建阶段，所以不能作为发布活动功能失败判断。

### 发布活动

当前状态：已复跑通过，但耗时仍接近 15 分钟，需要继续优化。

上一轮现象：

- 命令超过 15 分钟外层超时。
- 没有生成新的失败快照，推断 pytest 进程被外部 timeout 杀掉，fixture 未执行失败截图保存。
- 历史快照曾显示活动最终进入 `我的活动` 列表并出现 `待审` 活动记录，因此后续需区分“业务未通过”和“流程耗时/成功态识别过慢”。

本轮执行命令：

```bash
PYTHONPATH=apps/velowind-app/appium python3 -m pytest \
  'apps/velowind-app/appium/tests/activity/test_ios_publish_activity.py::test_user_can_publish_activity_for_review' \
  -q -m full
```

本轮结果：

```text
1 passed, 1 warning in 895.19s (0:14:55)
```

当前效果判断：

- 用例已经可以在真机通过。
- 耗时仍然接近 15 分钟，优化不充分。
- 人工观察到首页进入后点击发布按钮前等待较明显。
- 当前 `_tap_publish_entry_if_present()` 仍然先尝试多个 accessibility id 和文本候选，最后才坐标点击底部发布入口。下一步应将首页发布入口改为优先坐标点击，避免不存在的候选逐个短等待。
- 已继续调整：`_tap_publish_entry_if_present()` 现在优先坐标点击底部发布入口，再走 accessibility id、文本和 XPath 兜底。
- 调整后本地活动 helper 已通过：

```text
24 passed, 1 warning in 0.03s
```
- 调整后发布活动真机复跑通过：

```text
1 passed, 1 warning in 875.84s (0:14:35)
```
- 对比上一轮 `0:14:55`，仅减少约 20 秒，说明首页发布入口不是主要耗时。下一步应处理测试数据复杂度和编辑器输入成本。
- 开启 `VW_ACTIVITY_PROFILE=1` 后的首次分阶段耗时如下：

```text
[activity-profile] open-publisher: 24.29s
[activity-profile] upload-image: 141.00s
[activity-profile] fill-title: 13.84s
[activity-profile] select-activity-type: 9.25s
[activity-profile] select-province: 9.07s
[activity-profile] fill-city: 13.56s
[activity-profile] fill-description: 88.51s
[activity-profile] fill-itinerary: 210.20s
[activity-profile] fill-known-text-fields: 182.28s
[activity-profile] resolve-picker-fields: 3.50s
[activity-profile] fill-form: 675.47s
[activity-profile] submit-for-review: 9.99s
1 passed, 1 warning in 772.49s (0:12:52)
```

结论：

- 最大热点不是提交阶段，而是表单填写。
- 其中 `fill-known-text-fields` 有明显无效 XPath 搜索成本，优先值得优化。

针对上述热点已继续调整：

- `_fill_input_near_label()` 增加关键字预筛。
- `_fill_known_text_fields()` 删除重复 `城市名称` 填写。
- 发布活动图片选择改为指定相册后单选首张图，共享 `photo_picker` 默认行为不变。

调整后再次开启 profile 的真机结果：

```text
[activity-profile] open-publisher: 24.26s
[activity-profile] upload-image: 93.18s
[activity-profile] fill-title: 17.20s
[activity-profile] select-activity-type: 9.24s
[activity-profile] select-province: 9.27s
[activity-profile] fill-city: 17.05s
[activity-profile] fill-description: 88.74s
[activity-profile] fill-itinerary: 209.52s
[activity-profile] fill-known-text-fields: 62.99s
[activity-profile] resolve-picker-fields: 3.48s
[activity-profile] fill-form: 514.92s
[activity-profile] submit-for-review: 9.92s
1 passed, 1 warning in 613.17s (0:10:13)
```

本轮优化效果：

- 相比 `0:12:52` 再缩短 `2:39`。
- 相比最初记录的 `0:14:55` 总共缩短 `4:42`。
- `fill-known-text-fields` 从 `182.28s` 降到 `62.99s`，减少约 `119s`。
- `upload-image` 从 `141.00s` 降到 `93.18s`，减少约 `48s`。
- 当前剩余最大热点已变为：
  - `fill-itinerary: 209.52s`
  - `upload-image: 93.18s`
  - `fill-description: 88.74s`

继续拆解 `fill-itinerary` 后发现，真正的大头不是字段定位，而是编辑器内每次输入后的收键盘：

```text
[activity-profile] itinerary-0-fill-title: 6.76s
[activity-profile] itinerary-0-dismiss-after-title: 11.05s
[activity-profile] itinerary-0-fill-subtitle: 6.58s
[activity-profile] itinerary-0-dismiss-after-subtitle: 11.26s
[activity-profile] itinerary-0-fill-body: 6.90s
[activity-profile] itinerary-0-dismiss-after-body: 31.30s
...
[activity-profile] itinerary-1-dismiss-after-body: 33.95s
```

根因判断：

- 编辑器填写过程沿用了通用 `_dismiss_editor_keyboard()`。
- 该路径会优先尝试多组 `hide_keyboard()`，在编辑器场景下非常慢。
- 真机上“点击编辑器安全区域收起键盘”即可生效，没必要每次都走通用慢路径。

已完成改动：

- 保留原有 `_dismiss_editor_keyboard()`，避免影响编辑器关闭流程的稳妥性。
- 新增 `_dismiss_editor_keyboard_fast()`，仅用于编辑器填写过程：
  - 优先点击编辑器安全区域收键盘。
  - 失败时再回退到原来的稳妥路径。
- `_fill_itinerary_editor_item()` 与“新增行程段前”的收键盘切换为快速路径。

调整后 profile 结果：

```text
[activity-profile] itinerary-0-fill-title: 6.75s
[activity-profile] itinerary-0-dismiss-after-title: 3.25s
[activity-profile] itinerary-0-fill-subtitle: 6.61s
[activity-profile] itinerary-0-dismiss-after-subtitle: 3.25s
[activity-profile] itinerary-0-fill-body: 6.92s
[activity-profile] itinerary-0-dismiss-after-body: 3.34s
[activity-profile] itinerary-0-fill-item: 30.12s
[activity-profile] itinerary-1-dismiss-before-add: 3.23s
[activity-profile] itinerary-1-add-segment: 25.53s
[activity-profile] itinerary-1-fill-title: 7.43s
[activity-profile] itinerary-1-dismiss-after-title: 3.27s
[activity-profile] itinerary-1-fill-subtitle: 6.88s
[activity-profile] itinerary-1-dismiss-after-subtitle: 3.29s
[activity-profile] itinerary-1-fill-body: 7.57s
[activity-profile] itinerary-1-dismiss-after-body: 3.41s
[activity-profile] itinerary-1-fill-item: 31.85s
[activity-profile] fill-itinerary: 119.04s
1 passed, 1 warning in 523.02s (0:08:43)
```

新增效果：

- `fill-itinerary` 从 `209.52s` 降到 `119.04s`，减少约 `90s`。
- 整体发布活动真机从 `0:10:13` 进一步降到 `0:08:43`，再缩短 `1:30`。
- 相比最初记录的 `0:14:55`，总共缩短 `6:12`。

继续分析后发现，`fill-description` 的主要耗时并不在输入，而在编辑器关闭前的收键盘。此前 `description-close-editor` 约为 `38s`，原因与活动行程一致：关闭编辑器前仍默认走了慢的通用收键盘路径。

已完成改动：

- `_close_editor()` 前两次收键盘改为优先 `_dismiss_editor_keyboard_fast()`。
- 仍保留原有慢路径回退和后续关闭兜底，不改变失败时的保护逻辑。

调整后 profile 结果：

```text
[activity-profile] description-open-editor: 10.48s
[activity-profile] description-fill-editor: 36.52s
[activity-profile] description-close-editor: 12.98s
[activity-profile] fill-description: 63.56s
[activity-profile] fill-itinerary: 119.38s
1 passed, 1 warning in 498.27s (0:08:18)
```

新增效果：

- `description-close-editor` 从约 `38s` 降到 `12.98s`，减少约 `25s`。
- `fill-description` 从约 `88.74s` 降到 `63.56s`，减少约 `25s`。
- 整体发布活动真机从 `0:08:43` 进一步降到 `0:08:18`，再缩短 `25s`。
- 相比最初记录的 `0:14:55`，总共缩短 `6:37`。

继续针对“进入 App 后点击底部 `+` 发布”这段做了更激进的优化：

- 点击首页发布按钮后，优先直接坐标点击“活动”类型。
- 不再先等待发布类型 sheet 的文本信号，再决定是否点击活动类型。
- 如果没有直接进入活动表单，仍回退到原来的 id/text 兜底逻辑。

调整后 profile 结果：

```text
[activity-profile] open-publisher: 21.04s
1 passed, 1 warning in 496.44s (0:08:16)
```

效果：

- `open-publisher` 从 `24.28s` 降到 `21.04s`，减少约 `3s`。
- 整体发布活动从 `0:08:18` 进一步降到 `0:08:16`。

随后继续对图片链路做分阶段埋点，确认 `upload-image` 的主要热点为：

```text
[photo-picker-profile] choose-source: 15.04s
[photo-picker-profile] dismiss-alerts-initial: 7.38s
[photo-picker-profile] wait-library-visible-initial: 7.31s
[photo-picker-profile] open-photo-album: 14.64s
[photo-picker-profile] tap-photo-grid-candidate: 11.37s
[photo-picker-profile] confirm-system-selection: 27.66s
[photo-picker-profile] choose-local-photo-primary: 53.68s
[activity-profile] upload-image: 86.16s
1 passed, 1 warning in 487.63s (0:08:07)
```

基于这份细分 profile，已完成两类优化：

1. `choose_local_photo()` 增加更细粒度埋点，明确相册切换、缩略图点击、完成确认的各自耗时。
2. `confirm_system_photo_picker_selection()` 改成更主动的快路径：
   - 不再每轮先依赖 `page_source` 判断是否可点完成。
   - 直接尝试点击 `Add/完成`。
   - 点击成功后立即等待 picker 退出。

调整后 profile 结果：

```text
[photo-picker-profile] choose-source: 15.12s
[photo-picker-profile] dismiss-alerts-initial: 7.54s
[photo-picker-profile] wait-library-visible-initial: 7.33s
[photo-picker-profile] open-photo-album: 14.53s
[photo-picker-profile] tap-photo-grid-candidate: 11.16s
[photo-picker-profile] confirm-system-selection: 23.89s
[photo-picker-profile] choose-local-photo-primary: 49.58s
[activity-profile] upload-image: 82.21s
1 passed, 1 warning in 484.99s (0:08:04)
```

效果：

- `confirm-system-selection` 从 `27.66s` 降到 `23.89s`，减少约 `4s`。
- `upload-image` 从 `86.16s` 降到 `82.21s`，减少约 `4s`。
- 整体发布活动从 `0:08:07` 进一步降到 `0:08:04`。

最后又将发布活动/发布笔记两条主链路的“准备首页”改成发布专用快速路径：

- 新增 `ensure_logged_in_for_publish_entry()`。
- 不再强依赖首页 feed 完整 ready。
- 只要确认不在登录页、也不在发布页/详情页阻塞场景，就直接准备点击底部 `+`。
- 登录后如果已经回到可发布首页，不再额外做一次首页恢复。

调整后最新真机结果：

```text
[activity-profile] open-publisher: 20.82s
[activity-profile] upload-image: 81.84s
[activity-profile] fill-form: 387.99s
1 passed, 1 warning in 471.06s (0:07:51)
```

本轮累计效果：

- `open-publisher` 从 `21.20s` 降到 `20.82s`。
- `upload-image` 从 `82.21s` 进一步降到 `81.84s`。
- 整体发布活动从 `0:08:04` 进一步降到 `0:07:51`。
- 相比最初记录的 `0:14:55`，总共缩短 `7:04`。

继续拆解 `fill-known-text-fields` 后发现，这段耗时主要来自重复拉取 `page_source` 和对当前页面不存在的字段做多轮 XPath 探测：

```text
[activity-profile] known-field-contact-name: 13.99s
[activity-profile] known-field-contact-phone: 10.49s
[activity-profile] known-field-location: 17.41s
[activity-profile] known-field-max-participants: 10.44s
[activity-profile] known-field-fee: 10.44s
[activity-profile] fill-known-text-fields: 62.76s
1 passed, 1 warning in 469.62s (0:07:49)
```

已完成改动：

- `_fill_known_text_fields()` 只读取一次当前 `page_source`。
- 每组字段先做关键词预筛；如果该组关键词完全不在当前页面，整组跳过。
- `_fill_input_near_label()` 支持传入已读取的 `page_source`，避免每个关键词重复读取页面源码。

调整后 profile 结果：

```text
[activity-profile] known-field-contact-name: 0.00s
[activity-profile] known-field-contact-phone: 0.00s
[activity-profile] known-field-location: 0.00s
[activity-profile] known-field-max-participants: 0.00s
[activity-profile] known-field-fee: 0.00s
[activity-profile] fill-known-text-fields: 3.53s
[activity-profile] fill-form: 330.25s
1 passed, 1 warning in 412.91s (0:06:52)
```

新增效果：

- `fill-known-text-fields` 从 `62.76s` 降到 `3.53s`，减少约 `59s`。
- 整体发布活动从 `0:07:51` 进一步降到 `0:06:52`。
- 相比最初记录的 `0:14:55`，总共缩短 `8:03`。

继续回到 `upload-image`，针对 `choose-source`、权限弹窗探测和完成按钮做轻量定位优化：

- `choose_photo_library_source()` 优先使用 iOS predicate 精确匹配相册入口文案，减少 XPath 查找。
- `dismiss_photo_permission_alerts()` 先读取一次 `page_source`，没有权限弹窗文案时直接跳过，不再固定探测多个按钮。
- `_tap_photo_picker_done_button()` 优先使用 accessibility id `Add` 和 iOS predicate 匹配 `完成/添加`，最后才走 XPath 兜底。

调整后 profile 结果：

```text
[photo-picker-profile] choose-source: 3.05s
[photo-picker-profile] dismiss-alerts-initial: 4.54s
[photo-picker-profile] wait-library-visible-initial: 7.45s
[photo-picker-profile] open-photo-album: 14.62s
[photo-picker-profile] tap-photo-grid-candidate: 11.23s
[photo-picker-profile] confirm-system-selection: 20.48s
[photo-picker-profile] choose-local-photo-primary: 46.33s
[activity-profile] upload-image: 64.01s
[activity-profile] fill-form: 311.34s
1 passed, 1 warning in 392.89s (0:06:32)
```

新增效果：

- `choose-source` 从约 `15s` 降到 `3.05s`，减少约 `12s`。
- `confirm-system-selection` 从约 `23.9s` 降到 `20.48s`，减少约 `3.4s`。
- `upload-image` 从 `81.81s` 降到 `64.01s`，减少约 `18s`。
- 整体发布活动从 `0:06:52` 进一步降到 `0:06:32`。
- 相比最初记录的 `0:14:55`，总共缩短 `8:23`。

### 发布笔记

当前状态：本轮活动优化后已复跑通过。

最近一次已知通过命令：

```bash
PYTHONPATH=apps/velowind-app/appium python3 -m pytest \
  'apps/velowind-app/appium/tests/message/test_ios_publish_note.py::test_user_can_publish_note_for_review[publish-note-changbaishan]' \
  -q -m full
```

已知结果：

```text
1 passed, 1 warning in 488.41s (0:08:08)
```

本轮复跑结果：

```text
1 passed, 1 warning in 449.67s (0:07:29)
```

结论：

- 活动侧短等待、发布入口坐标优先、2 段行程数据调整没有破坏发布笔记长白山流程。
- 共享 `photo_picker` 默认“指定相册后全选”的行为仍可支持发布笔记真机用例通过。
- 活动侧新增的“指定相册后单选首图”策略没有影响笔记主链路。
- 发布专用首页准备 helper 也没有破坏发布笔记长白山真机流程。
- 相册入口和完成按钮的 predicate 快路径没有破坏发布笔记长白山真机流程。

## 下一步计划

1. 继续优化 `upload-image()`，当前剩余最大的图片热点是：
   - `open-photo-album`，约 `14.6s`
   - `tap-photo-grid-candidate`，约 `11.2s`
   - `confirm-system-selection`，约 `20.5s`
2. 可继续评估 `open-photo-album()` 是否能减少相册标题 XPath 检查，或针对固定相册位置增加更轻的坐标/谓词路径。
3. `fill-known-text-fields()` 已从约 `63s` 降到 `3.5s`，后续不再作为优先优化点。
4. 首页发布入口和发布专用首页准备路径已经有明显收益，后续不应再优先投入这里，除非产品页面结构再次变化。
5. 保持 2 段行程数据，除非产品校验规则变化；单段行程已被真机证明无法稳定保存。
6. 每次活动侧优化后都复跑发布活动和发布笔记长白山真机用例，保证共享 `photo_picker` 两条主流程都通过。

## 发布笔记联动优化

用户观察到两个笔记发布体验问题：

- 进入 App 后，等待较久才点击底部 `+`。
- 选择“笔记”后，添加图片前等待较久。

已完成改动：

- `publish_message_note()` 增加默认关闭的 `VW_ACTIVITY_PROFILE=1` 分段 profile。
- `open_message_note_publisher()` 的底部发布入口优先走坐标点击，再走 id/text/XPath 兜底。
- `_tap_note_image_plus()` 优先坐标点击图片占位区域，再走 id/text/XPath 兜底。
- `_clear_existing_note_images()` 增加页面源码预筛；只有出现 `删除/移除/已选择` 等旧图迹象时，才扫描删除按钮。

首次拆解结果：

```text
[note-profile] open-publisher: 13.61s
[note-profile] upload-clear-existing-images: 17.43s
[note-profile] upload-tap-image-plus: 2.65s
[note-profile] upload-choose-photo-library: 92.76s
[note-profile] upload-image: 112.84s
1 passed, 1 warning in 419.13s (0:06:59)
```

优化后结果：

```text
[note-profile] open-publisher: 13.75s
[note-profile] upload-clear-existing-images: 2.67s
[note-profile] upload-tap-image-plus: 2.65s
[note-profile] upload-choose-photo-library: 93.37s
[note-profile] upload-image: 98.69s
1 passed, 1 warning in 403.81s (0:06:43)
```

效果：

- `upload-clear-existing-images` 从 `17.43s` 降到 `2.67s`，减少约 `15s`。
- 发布笔记长白山从 `0:06:59` 降到 `0:06:43`。
- 选择笔记后、添加图片前的等待主要来自“扫描旧图片删除按钮”，当前已通过预筛明显降低。
