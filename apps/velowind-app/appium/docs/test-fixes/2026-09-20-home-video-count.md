# 2026-09-20 首页视频检查数量可配置

## 范围与当前状态

- 用户要求：当前 App 只有 2 个视频，默认检查数量降为 2，并做成配置变量。
- 用例：`tests/message/test_home_video_playback.py::test_four_home_videos_play_normally`。
- 模块：`velowind_appium/modules/home_video_playback.py`。
- 当前状态：单元测试通过；真机及整套未验证。最后核实：2026-09-20。
- 历史参考：[Android 候选不足](2026-09-15-android-video-candidates.md)、[iOS 模拟器筛选](2026-09-16-ios-simulator-video-discovery.md)。历史定位问题不作为本次原因；本次按用户明确要求调整样本数量。

## 失败证据

- 现场信息来自用户：当前版本只有 2 个视频；未采集新的真机截图、XML 或失败报告，App 具体版本未核实。
- 当前代码确认公共函数将目标数量、日志、失败信息硬编码为 4；只有两个不同视频时不能满足旧目标。

## 第 1 轮：分析、修改与验证

### 分析

- 已确认：目标数量硬编码；用例未传入可配置数量。
- 未确认：当前设备实际候选数量与播放状态，需真机另行核实。

### 修改

- 用例增加 `HOME_VIDEO_COUNT`，读取环境变量 `VW_HOME_VIDEO_COUNT`，默认 `2`；步骤名称同步配置值。
- 公共函数增加关键字参数 `video_count`，用于完成条件、日志及报错；拒绝非正数。
- 保留旧函数名、用例名及公共函数默认值 4，兼容已有调用和用例选择；该目标用例显式传入默认值 2。
- 保留视频去重、播放断言和两个播放失败立即终止规则。
- 扩展现有阈值测试覆盖两个视频全部成功和一个播放失败。

### 验证

```bash
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_home_video_playback.py -q
```

- 单元结果：43 passed，0.65 秒；有既有 urllib3 / LibreSSL 环境警告。
- 运行目录：`.tmp/appium-ios/runs/20260920-100403-34507/`；无真机 Allure 报告或临时 URL。
- 真机验证：未执行；整套：未验证。
- 清理验证：不涉及，无新增业务数据。
- 本轮结论：离线验证通过，无失败修改尝试；不代表真机播放通过。

## 可复用方法与无效尝试

- 运行时可设置 `VW_HOME_VIDEO_COUNT=4` 调整样本数，不需要修改公共检查逻辑。
- 本轮无无效尝试。

## 遗留项与交接

- 已完成：默认检查 2 个、环境变量配置、动态报告数量及单元回归。
- 未验证：真机执行与整套；本轮未创建设备会话，未检查设备占用。
- 下一步：需要真机验证时，先检查 Appium / pytest 进程，避免竞争设备，再运行目标用例。
