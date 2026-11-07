# 2026-10-27 API 清理刚发布笔记返回不存在

## 范围与当前状态

- 用户要求：修复图片发布测试用例，并确认照片权限已授予。
- 用例：`test_user_can_publish_note_for_review[publish-note-changbaishan]`，iOS 真机。
- 模块：`note_api_cleanup.py` / `cleanup_config.py`，当前模式 api。
- 当前状态：独立生产配置与有效凭据已接入；完整目标真机 1 passed，本轮新增笔记实际删除成功；旧 ID 在生产查询不存在，未声称由本轮删除；最后核实 2026-10-27。
- 历史参考：[清理环境配置历史](2026-09-20-note-cleanup-login-password.md)、[测试环境映射](2026-10-19-test-api-environment.md)。历史 App 环境不能代表当前安装包环境。

## 失败证据

- run `.tmp/appium-ios/runs/20261027-publish-entry-fixed-full/`，源于 [入口修复](2026-10-27-ios-publish-entry-transition.md) 后完整验证。
- 发布与图片内容校验 passed；清理失败使整条 **1 failed / 172.83 秒**。
- publication ID `pst-5227a8b35dcf4759ad3db2daf77dbb5f`，唯一标题 `50736b29-测试 - 长白山真的有`。
- DELETE `https://dev-api.velowind.com/api/v1/mobile/posts/pst-5227a8b35dcf4759ad3db2daf77dbb5f`，HTTP 400 / code `17210004` / `post.not_found`。
- 响应 traceId `6a589c90-a8f1-4973-947e-48fe7b0f1e9a`，时间 2026-10-27 15:33:47（Asia/Shanghai）。
- Allure 附件 `allure-results/f6d10e1c-9add-4bbe-9808-b40956f6a85e-attachment.txt`（删除响应）、`4f3993b6-28e7-4f2d-8c61-8f4a0c2b8b9d-attachment.txt`（publication ID）。不在记录复制认证附件。

## 第 1 轮：核对调用证据与环境

### 分析

- 已确认：登录成功后请求正确格式的已捕获 ID，删除接口明确返回不存在。代码没有把 HTTP 400 当作成功，也没有按标题删除其他笔记。
- 待确认：App 当前连接环境是否与 cleanup.yaml 固定的 dev-api 一致。已请求用户确认，不能用历史测试环境结论代替当前环境。
- 未确认：是否为环境错配、服务端可见性规则或其他后端问题；没有服务端日志 / DB / Redis 证据，不给后端确定性根因。

### 修改与验证

- 本轮无清理代码修改，未重复发布或跨环境发送凭据。
- 实际清理：失败，新增笔记尚未确认删除；遗留 ID 如上。
- 真机发布：已通过；完整用例：失败；清理：失败，分别记录。
- 下一步：确认 App 环境。若配置错配，修正运行环境后清理上述唯一 ID并复跑；若环境一致，继续服务端只读取证。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| 分开检查发布断言、API 登录和删除响应 | 整条失败在清理 | 本次发布成功且登录成功，失败点为 DELETE post.not_found |

## 遗留项与交接

- 待清理：`pst-5227a8b35dcf4759ad3db2daf77dbb5f`。
- 尚未验证：完整目标通过与实际删除。
- 当前设备会话已正常退出，无其他正在运行的设备 pytest；未终止他人 Appium / WDA。

## 第 2 轮：用户确认生产环境，修正地址后登录被拒绝

### 分析与修改

- 用户明确当前 App 为生产环境，并确认 API URL `https://prod-api.velowind.com`。因此前轮向 dev-api 清理与当前 App 环境不一致；此处为测试环境配置错配，不据此归因为后端缺陷。
- `cleanup.yaml` 的 `note_cleanup_api_base_url` 从 dev-api 改为用户确认的 prod-api。`README.md` 同步当前默认环境说明，保留显式 `VW_API_ENV=test|uat|prod` 覆盖能力。
- 按已保存唯一 ID `pst-5227a8b35dcf4759ad3db2daf77dbb5f` 尝试生产清理，未重新发布。登录 POST 返回 HTTP 400，尚未执行 DELETE。
- 首次恢复脚本只收集 DELETE 响应，登录失败导致 `delete-result.json` 为 `[]`，不能据此判定请求未发生。随后单独进行一次脱敏登录诊断，不保存请求体或完整认证响应，确认 HTTP 400 / code `10011023` / `Incorrect password`，traceId `01b81ef8-92d3-416a-994f-2d6ba090e1f2`。
- 证据目录 `.tmp/appium-ios/runs/20261027-prod-cleanup-recovery/`，摘要 `login-summary.json`。记录不含凭据。
- 已请求用户更新本地 `ios-appium.yaml` 的 login 配置或提供现有有效配置路径；未猜测密码，未重复发起发布，不将 dev-api 登录成功当作生产登录成功。

### 验证

```bash
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_note_api_cleanup.py apps/velowind-app/appium/tests/unit-test/test_cleanup_config.py -q
```

- 单元：**41 passed / 0.08 秒**，既有 LibreSSL warning；`git diff --check` 通过。
- 配置：恢复脚本实际解析为 `https://prod-api.velowind.com/api/v1/mobile`，请求地址正确。
- 生产登录：**失败**；实际删除：**未执行**；遗留笔记：**尚未清理**。
- 本轮未新建设备会话、未复跑完整发布用例；上一轮完整用例失败保持不变。

## 当前交接状态

- 已完成：发布入口修复、真机发布与图片内容校验、默认生产清理地址修正；消息/相册单元 307 passed，API/配置单元 41 passed（不同测试集，分别记录）。
- 待用户更新有效生产凭据后：先登录预检，再按保存 ID 清理上一轮新增笔记；成功后检查设备占用并运行完整目标用例，独立核对 cleanup-result 和 API 删除响应。
- 未完成：生产残留删除、完整目标用例通过。没有把清理 HTTP 400 或未执行删除记为成功。

## 第 3 轮：独立生产配置文件

- 用户要求“要设置生产环境的配置文件”，并选择提供其他有效配置路径；目前尚未收到具体路径。
- 创建本地 `apps/velowind-app/appium/ios-appium.prod.yaml`，复用当前真机设备配置，设置 `no_reset: true`，同时包含生产 `cleanup`（prod-api、api 模式、成功后自动删除）。`login.username/password` 留空，不把已被生产拒绝的凭据复制为有效生产配置。
- `.gitignore` 加入该具体本地文件路径，文件权限 0600。README 补充同时设置 `VW_APPIUM_CONFIG_FILE` 与 `VW_APPIUM_CLEANUP_CONFIG_FILE` 的运行命令；复用已有加载逻辑，没有新增配置加载代码。
- 实际加载检查：device 目标、no_reset=true、生产 API 基础地址、api 模式、自动删除设置均通过，登录字段按预期为空。`git check-ignore` 确认生产配置被忽略。
- 配置相关单元：`VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_config.py apps/velowind-app/appium/tests/unit-test/test_cleanup_config.py -q`，**27 passed / 0.06 秒**。`git diff --check` 通过。
- 当前状态：生产配置结构已就绪，待用户提供有效配置文件绝对路径或填写本地生产 login 后继续。未执行新 API 登录、真机发布或删除；遗留笔记与完整验证状态不变。

## 第 4 轮：收到生产账号文件路径，文件为空

- 用户提供 `/Users/test/Documents/velowind-app-dev-test/.private/message-regression/prod_accounts.json`。
- 首次 JSON 读取出现 `JSONDecodeError`；随后只检查文件大小，确认路径存在、**0 字节**，并非账号结构不兼容。未打印文件内容或凭据。
- 已将该私有文件权限设为 0600，未改写其内容；该目录已由 Git 忽略。
- 已请用户填写并保存有效生产账号，提示可沿用现有消息回归的 `accounts.a.username/password` 结构，并使用发布笔记的同一账号。
- 尚未接入空凭据、未请求生产登录、未发送 DELETE、未建立真机会话。本轮无新增测试数据。待文件写入有效内容后继续生产清理及完整目标验证。

### 第 4 轮接续：文件写入后核实为原测试配置引用

- 后续观察该文件已写入 529 字节并可解析 JSON，故继续读取结构；不将最初空文件的失败覆盖。
- 文件实际为执行配置包装层：`api_origin=https://dev-api.velowind.com`，`accounts_file=accounts.json`（相对于同目录），账号角色 A 使用变量映射；相关环境变量未设置。
- 解析其引用的本地账号文件后，仅做值比较，不输出账号密码：账号 A 与当前发布账号相同，密码与刚被生产接口拒绝的值也相同。B/C 是不同账号，未尝试用其他账号删除 A 的笔记。
- 此文件尚未提供新的有效生产凭据；不能因为文件名含 prod 就当作生产配置，也不能使用其 dev-api 地址覆盖用户已确认的生产 host。
- 已请用户更新生产账号凭据或提供正确路径。未重新提交相同的已拒绝凭据，未新建真机会话、未发布、未删除，生产 yaml 登录仍留空。

## 第 5 轮：用户更新后生产登录成功，原 ID 在生产查询不存在

- 用户确认已更新生产账号凭据。第一次重读仍读到旧 A 配置，接入后生产预检仍 10011023；随后复核结构发现文件已更新为 `accounts.admin.userName/password`，更正为当前文件中的明确账号，不尝试 B/C。
- 仅做脱敏值比较，当前账号与发布账号相同，密码已更新。将有效凭据写入已忽略的本地 `ios-appium.prod.yaml`（0600），不写入聊天、记录或 Git。
- 新凭据生产登录 **HTTP 200 / code 0**。对保存唯一 ID 的 DELETE 仍 **HTTP 400 / 17210004**；响应 traceId `5106e478-e710-4b2f-aa2a-cc7fe61c79a8`。证据 `20261027-prod-cleanup-recovery/delete-result-current-credentials.json`，不含认证响应。
- 随后只读 GET `/posts/mine/<ID>`、`/posts/<ID>` 均返回 17210004；`/posts/mine?status=ALL&pageNo=1&pageSize=20` 成功返回 4 条，无对应 ID 或唯一标题。没有确认删除成功，不将不存在强行改写为 deleted。
- 原 ID 当前在生产查询中不存在；是否曾被外部删除或原发布环境不同尚未确认，不给后端根因。仅检查本账号有限列表，未跨环境查询或修改其他笔记。
- 检查无其他设备 pytest 后，启动使用独立生产配置的完整目标 `20261027-prod-publish-final`。当前运行中，尚未计通过；本轮将核对新发布 ID、发布断言和实际 API 删除。

```bash
VW_APPIUM_CONFIG_FILE="$PWD/apps/velowind-app/appium/ios-appium.prod.yaml" VW_APPIUM_CLEANUP_CONFIG_FILE="$PWD/apps/velowind-app/appium/ios-appium.prod.yaml" VW_API_ENV=prod VW_APPIUM_RUN_ID=20261027-prod-publish-final VW_APPIUM_ARTIFACT_DIR=.tmp/appium-ios/runs/20261027-prod-publish-final/artifacts VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest 'apps/velowind-app/appium/tests/message/test_ios_publish_note.py::test_user_can_publish_note_for_review[publish-note-changbaishan]' -q -s --tb=short --alluredir=.tmp/appium-ios/runs/20261027-prod-publish-final/allure-results
```

### 第 5 轮完整复跑结果：设备锁屏，setup 失败

- `20261027-prod-publish-final`：**1 setup error / 4.58 秒**。WDA 报 `Unable to launch com.velowind.rider because the device was not, or could not be, unlocked`，`BSErrorCodeDescription=Locked`。
- 未进入准备、发布或清理步骤，无本轮新增笔记。生产登录预检成功不代表真机用例通过。
- 已请求用户解锁并保持屏幕亮起后再复跑；未尝试绕过设备锁屏。
- 当前状态：生产配置与凭据已接入且 API 登录成功；原 ID 在生产私有/公开查询均不存在，删除未被接口确认；完整目标待解锁后复验。

## 第 6 轮：用户解锁后完整复跑

- 用户确认“已解锁，继续复跑”。检查无其他设备 pytest 后，使用相同生产配置启动 `20261027-prod-publish-unlocked`。
- 命令与第 5 轮相同，只将 `VW_APPIUM_RUN_ID`、artifact 和 allure 目录改为该 run。当前运行中，不计为通过。
- 使用有效生产账号及 prod-api，保留 App 数据和照片权限；未更改用户提供的私有 JSON 内容。

### 第 6 轮最终结果：完整目标通过，本轮新增笔记实际删除

- `20261027-prod-publish-unlocked`：**1 passed / 166.91 秒**；首页准备 1.9 秒、发布与图片校验 159.4 秒、清理 0.7 秒均 passed。
- 本轮 publication：`pst-b628261e44844719a4afc8050ae94ab2`，唯一标题 `944aeb92-测试 - 长白山真的有`。
- 生产 DELETE `https://prod-api.velowind.com/api/v1/mobile/posts/pst-b628261e44844719a4afc8050ae94ab2` 返回 **HTTP 200 / code 0 / postId 匹配 / deleted=true**，traceId `e8fe7e75-9eee-45be-99d3-1d9210b87fd8`。
- `publish-note-cleanup-result` 明确 deleted 为原请求标题、skipped=[]，**无 cleanup-pending**；本轮新增笔记无清理遗留。
- 用户补充可通过不同账号确定环境。本轮 App 刚发布并从 UI 唯一标题捕获的 ID，在生产 API 被同账号成功删除，这已形成当前 App 使用生产环境的直接证据，无需额外切换账号或产生测试内容。
- Allure HTML 已实际生成：`.tmp/appium-ios/runs/20261027-prod-publish-unlocked/allure-report/`；原始结果同目录 `allure-results/`。
- 原 ID `pst-5227a8b35dcf4759ad3db2daf77dbb5f` 在生产私有详情、公开详情和有限本人列表均未查询到，历史 DELETE 没有成功确认，不将本轮新 ID 的删除成功覆盖原 ID 的结果。
- 本轮只验证指定图片发布参数用例，**整套未验证**。会话已正常退出，未停止他人服务。

## 最终交接

- 已完成：发布入口有限重试、独立生产配置、有效生产凭据接入、完整目标真机通过、本轮新增笔记 API 删除确认、修复文档与索引更新。
- 单元：消息/相册 307 passed，API/清理配置 41 passed，设备/清理配置 27 passed（各阶段有重叠，不合并计数）；`git diff --check` 通过。
- 生产私有 YAML 含有效登录配置，已 Git 忽略、0600；用户原 JSON 内容未被改写。后续凭据变化需同步本地生产 YAML，未新增自动 JSON 导入机制。
- 未完成范围：整套回归未执行；旧 ID 的历史消失原因未追溯，不影响本轮目标通过结论。
