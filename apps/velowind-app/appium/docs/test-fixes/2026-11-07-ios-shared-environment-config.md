# 2026-11-07 iOS 登录与清理共用环境配置

## 范围与当前状态

- 用户要求：VW_API_ENV=prod 自动使用 ios-appium.prod.yaml，登录和清理使用同一套配置。
- 涉及模块：config.py、cleanup_config.py、environment_login.py、普通 iOS YAML、相关单元测试。
- 平台：iOS；Android 原清理文件和默认候选清单行为保留。
- 当前状态：113 项相关单元通过；本地生产文件选择和共用读取检查通过；真实登录、发布及删除未验证。
- 最后核实：2026-11-07。
- 历史参考：[环境登录](2026-10-27-app-environment-login.md)、[清理账号](2026-09-20-note-cleanup-login-password.md)。旧隐式候选清单行为与本轮明确要求不同，按用户要求调整，不沿用历史真机成功结论。

## 失败证据

- 静态确认：config.py 原默认固定 ios-appium.yaml，不随 VW_API_ENV 切换；cleanup_config.py 原独立读取 cleanup.yaml。
- 生产 YAML 已包含 cleanup，但原来需要两个文件环境变量才能共用。
- environment_login.py 原在 VW_API_ENV 存在时隐式读取私有候选清单，可能覆盖静态登录账号。
- 本轮没有新真机失败报告或截图。先前发布清理 HTTP 400 的根因未通过本轮真机复验证实，不能声称已修复该失败。

## 第 1 轮：分析、修改与验证

### 分析

- 已确认：登录与清理文件选择规则分离，VW_API_ENV 原先仅影响 API 地址及候选优先级。
- 推测：配置分叉可能造成账号与目标 API 环境不匹配；尚未证明这是先前 HTTP 400 的原因。

### 修改

- config.resolve_ios_config_file：显式 VW_APPIUM_CONFIG_FILE 优先；prod 自动选 ios-appium.prod.yaml；其他选 ios-appium.yaml。
- 生产文件缺失时报错，不回退普通账号。iOS 的旧清理文件变量若指向不同文件，在配置加载时即报错；同一路径允许保留。
- iOS 清理共用 config 读取函数；普通 ios-appium.yaml 补入原 cleanup.yaml 的完整 cleanup 段，不改账号。
- iOS 不再隐式读取私有候选清单。显式变量或 YAML candidates_file 仍可启用候选识别；匹配后 UI 和清理继续使用同一组匹配账号及地址。
- 保留单项环境变量覆盖及 Android 行为；未改变用例断言。

### 验证

执行两轮同一组定向单元回归。首轮 113 passed，随后将冲突检查前移公共解析器并补充登录加载断言，再执行：

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest \
  apps/velowind-app/appium/tests/unit-test/test_ios_shared_config.py \
  apps/velowind-app/appium/tests/unit-test/test_config.py \
  apps/velowind-app/appium/tests/unit-test/test_cleanup_config.py \
  apps/velowind-app/appium/tests/unit-test/test_environment_login.py \
  apps/velowind-app/appium/tests/unit-test/test_note_api_cleanup.py \
  -q --override-ini addopts=''
```

- 最终结果：113 passed，9.58 秒；现有 urllib3/LibreSSL 警告 1 项。日志：.tmp/ios-shared-config-verification.log；报告运行目录：.tmp/appium-ios/runs/20261107-133233-72932/。git diff --check 通过。
- 只读本地检查：prod 自动选中本地生产 YAML；登录与清理字典一致；凭据存在；默认候选识别关闭。未输出凭据。
- 真机用例断言：未验证。
- 实际清理：未调用删除接口，未验证；原 cleanup-pending 状态未改变。
- 无失败修复尝试；离线配置检查不能替代真机结果。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| 临时假账号区分配置来源 | 环境及显式路径回归 | 可确认读取来源，不证明真实账号有效 |
| 候选清单改为显式启用 | 需要跨环境识别 | 仍可尝试其他环境；普通 prod 不再隐式启用 |

## 遗留项与交接

- 已完成：共用解析器、普通 YAML 清理段迁移、保留 Android 行为、更新说明。
- 未完成：真实登录、发布、删除；本轮未处理先前残留数据。
- 下一步：以 VW_API_ENV=prod 新启动测试，删除运行配置中冲突的旧清理文件变量。固定账号运行不要显式启用候选清单。
- 本轮未建立或替换设备会话，也未停止现有 Appium、pytest 或诊断任务；设备占用未检查，真机验证前需先检查。


## 第 2 轮：2026-11-09 prod 配置选择复发

### 现场与失败基线

- 用户提供报告 `20261109-172411-94838`，并明确运行时指定 `VW_API_ENV=prod`。报告中清理登录地址为生产 API，失败为 POST HTTP 400。
- 当前 `config.py` 实际固定默认 `ios-appium.yaml`，`resolve_ios_config_file` 不存在；与第 1 轮记录不一致。本轮无法确认代码为何缺失，不将历史记录视为当前代码已修复。
- 先执行既有 `test_ios_shared_config.py`：**7 failed, 2 passed**，7.42s。报告 `.tmp/appium-ios/runs/20261109-173435-97169/`。失败覆盖解析器缺失、生产配置丢失回退、清理文件冲突和读取普通账号。
- 已确认 VW_API_ENV 原先仅在当前清理逻辑中切换 API 地址，没有切换 iOS YAML。此配置缺陷可能造成账号/环境错配，但本轮没有实际登录请求，不确认 HTTP 400 的完整根因。

### 修改与验证

- 恢复 `config.resolve_ios_config_file`：显式文件优先；prod 自动选择同目录 `ios-appium.prod.yaml`；生产文件缺失报错；iOS 清理文件冲突报错。现有 cleanup_config 已共用读取函数，无需重复修改。
- 命令：沿用第 1 轮五个配置/环境/清理测试文件，`--override-ini addopts=''`。
- 结果：**113 passed, 1 warning in 9.72s**；报告 `.tmp/appium-ios/runs/20261109-173510-97259/`。warning 为既有 LibreSSL 提示。
- 本地只读检查使用 `VW_API_ENV=prod`：实际选择生产 YAML，登录和清理读取字典一致，最终登录字段与所选文件一致；只输出布尔值，未输出凭据。
- 本轮没有改账号、没有真机重跑、没有重复发布或执行删除。断言/实际清理仍以原报告为准；真机修复后复验未验证。

### 当前状态与下一步

- 配置选择离线验证通过；HTTP 400 及原发布数据清理未解决。下一步使用新代码进行受控真机验证，保留原失败记录。


### 第 2 轮补充：原请求与本地配置比对

- 用户指出可能使用错误用户名/密码。本轮只读原报告的 API request/response，与两个本地 YAML 的 login 字段比较，未输出或写入凭据。
- 原请求 phone 与普通/生产配置用户名均相同；password 与普通 `ios-appium.yaml` 相同，与 `ios-appium.prod.yaml` 不同。确认本次清理登录使用了普通配置密码。
- 原响应 HTTP 400，业务码 `10011023`，message `Incorrect password`。确认原登录失败原因是接口拒绝所发送密码；恢复生产文件选择可纠正凭据来源，但生产配置密码是否当前有效仍未实请求验证。
- 原 Allure API request/response/api-call 附件均非空，经既有 HTTP 服务读取均为 200，大小分别 329/521/1042 字节。用户截图预览空白不是本次没有记录请求。浏览工具打开 localhost 被客户端阻止，尚未确认前端空白原因。
- 未重跑真机、未重新登录、未执行清理；原用例 broken 和清理遗留不变。
