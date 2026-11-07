# 2026-10-19 草稿保存后无法进入我的

## 范围与当前状态

- 用户要求：所有自动化 case 通过。
- 用例：`test_user_can_save_note_as_draft_and_open_me_page`；iPhone 17 / App 1.3.0 build 64 / dev-api。
- 当前状态：8 单元通过；真机复验待当前整套结束。最后核实 2026-10-19。
- 历史索引未找到草稿同类记录；视频及登录问题独立记录，不将其修复结论套用到草稿。

## 失败证据

- 运行 `20261019-device-test-full-r1`，目录 `.tmp/appium-ios/runs/20261019-device-test-full-r1/`；未启动临时报告服务。
- 草稿前 5 步 passed；`06-open-me-page` 21.1 秒失败：`Unable to enter the Me page after saving draft`。
- Allure 截图 `allure-results/5f7a675d-8d33-473b-b02d-60744a90425d-attachment.png`；XML `4ae6c922-7daa-4f32-b94a-a82a7183dbb8-attachment.xml`。
- 实际在笔记详情，留言输入框获得焦点且键盘弹出，没有底部我的 tab。

## 第 1 轮：分析、修改与验证

### 分析与修改

- 已确认：`_tap_me_tab` 在找不到真实 tab 时仍固定点击窗口 88%/93% 坐标，并无条件返回 True；详情截图表明该位置落入详情交互区而非导航。
- 尚未确认：草稿保存操作为什么返回该详情而非根页面；后续用逐步骤截图定位。不能以点击保存成功推断草稿持久化已核实。
- `draft_flow.py` 移除无导航依据的坐标回退；找不到 tab 时使用现有返回 helper 回到有根导航的页面，再定位我的。
- 保留最终我的页面断言；未跳过或吞掉失败。

### 验证

```bash
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest \
apps/velowind-app/appium/tests/unit-test/test_draft_flow_helpers.py -q
```

- 8 passed，0.02 秒；既有 LibreSSL warning。
- 新增覆盖：从详情先返回再点真实 tab；缺失 tab 不点击详情坐标。
- 真机复跑：未执行；当前整套仍运行，不创建竞争会话。
- 实际清理：未执行；草稿是否保留尚未核实。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| 无导航 ID 时固定点底栏位置 | 页面可能为详情 | 原实现误点留言区，不可继续使用 |

## 遗留项与交接

- 整套结束后单独复跑草稿并捕获每一步，核对草稿保存及我的页面实际状态。

## 第 2 轮：整套中真机复验通过

- 统一配置运行 `20261019-device-test-full-r2` 中目标 CASE PASSED，6 个步骤均 passed；最后 `open-me-page` 16.2 秒，最终我的页面断言通过。
- 报告目录 `.tmp/appium-ios/runs/20261019-device-test-full-r2/`，控制台 `.tmp/appium-ios/device-test-full-r2.log`。
- 本轮未开启每一步截图，没有以截图额外核实草稿箱持久化；结论仅为原完整用例 6 步及其断言通过。
- 实际草稿清理未执行；整套其他用例仍运行中。
