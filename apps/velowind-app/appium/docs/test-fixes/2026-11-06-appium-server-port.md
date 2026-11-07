# 2026-11-06 Appium 已启动但脚本连接被拒绝

## 范围与当前状态

- 用户要求：排查启动 Appium 后脚本仍失败。
- 用例：`tests.message.test_ios_publish_note#test_user_can_publish_note_for_review[publish-note-changbaishan]`。
- 涉及模块：iOS 配置、Appium 服务连接；在创建会话阶段失败。
- 当前状态：已确认服务端口不一致；服务就绪与配置覆盖已验证，完整真机用例未重跑。
- 最后核实时间：2026-11-06（Asia/Shanghai）。设备系统、App 版本未核实。
- 历史参考：[真机会话冲突](2026-09-15-ios-publish-cleanup.md#问题四独立验证与整套测试竞争会话)。本轮未发现 pytest 进程，未创建或替换设备会话。

## 失败证据

- 原报告：`http://127.0.0.1:52586/#suites/a315921332822b24a92de7455c3da80b/b3c7bb053d1424aa/`。
- 运行目录：`.tmp/appium-ios/runs/20261106-112704-17985/allure-report/`。
- Allure 状态 `broken`，0 个用例步骤；`POST /session` 连接 `127.0.0.1:4723` 时发生 `Connection refused` / `MaxRetryError`。
- 当前 Appium 进程参数为 `--address 127.0.0.1 --port 4725`。`4725/status` 返回 `ready: true`，`4723/status` 连接失败。
- 失败发生在连接服务阶段，没有可用于判断 App 行为的截图或 XML。

## 第 1 轮：分析、处理与验证

### 分析

- 已确认：`velowind_appium/config.py` 默认服务地址为 `http://127.0.0.1:4723`，通过环境变量 `VW_APPIUM_SERVER_URL` 覆盖。当前启动端口为 4725，原运行没有连接到该服务。
- 未验证：服务连通后是否还有设备、WDA 或业务步骤错误；不能以 `/status` 成功代替真机通过。

### 处理

- 不修改通用默认端口，不重启现有服务；在运行脚本的同一终端指定 `VW_APPIUM_SERVER_URL=http://127.0.0.1:4725`。
- 仅新增本记录并更新索引，未修改测试代码或现有用户配置。

### 验证

```bash
ps -axo pid,ppid,etime,command | rg -i 'appium|pytest|allure'
curl --max-time 5 -fsS http://127.0.0.1:4725/status
curl --max-time 5 -fsS http://127.0.0.1:4723/status
VW_APPIUM_SERVER_URL=http://127.0.0.1:4725 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -c 'from velowind_appium.config import load_ios_config; print(load_ios_config().server_url)'
```

- 实际结果：4725 服务就绪；4723 连接失败；配置加载输出 `http://127.0.0.1:4725`。
- 单元测试：未执行，无测试代码变更。
- 真机验证：未执行，原报告保持 broken，未声称目标用例通过。
- 清理结果：本次诊断未发布笔记、未产生清理数据；其他历史数据未核实。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 |
| --- | --- | --- |
| 比对失败报告连接地址、服务进程端口与 `/status` | 创建会话时报连接拒绝 | 本轮确认 4723 / 4725 不匹配 |
| 环境变量覆盖服务地址 | 复用已启动的自定义端口服务 | 配置加载已验证；完整真机未验证 |

## 遗留项与交接

- 在启动测试的同一终端执行 `export VW_APPIUM_SERVER_URL=http://127.0.0.1:4725`，然后重跑原命令；该变量不影响其他已打开终端。
- 下一轮若仍失败，应读取新报告，区分服务连接、建会话和业务断言错误。
- 检查时没有运行中的 pytest，存在 Appium 与多个静态 Allure 报告服务；未结束任何现有进程。
