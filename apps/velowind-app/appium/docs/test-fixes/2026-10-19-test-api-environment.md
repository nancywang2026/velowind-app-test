# 2026-10-19 测试环境 API Host 映射

## 范围与当前状态

- 用户要求：`VW_API_ENV=test` 使用 `https://dev-api.velowind.com`。
- 模块：API 登录及笔记清理配置；当前状态：41 单元通过，真机图片发布及 dev-api 实际清理步骤通过，整套仍运行中。
- 最后核实：2026-10-19。
- 历史参考：[API 清理环境配置](2026-09-20-note-cleanup-login-password.md)。历史 UAT 固定地址不适用于用户本轮明确的测试环境。

## 失败证据

- 原 `cleanup_config.py` 只支持 uat/prod，test 无独立映射；固定 YAML 地址会覆盖显式 `VW_API_ENV`。
- 用户已将 `cleanup.yaml` 地址改为 dev-api；本轮保留该地址，只删除过时 UAT 说明。
- 同一凭据对 dev-api 登录预检 HTTP 200 / code 0，accessToken 存在；未输出密码、token 或完整认证响应。
- 本问题无独立失败 Allure 报告；相关 UI 登录分析见[登录准备失败](2026-10-19-login-session.md)。

## 第 1 轮：修改与验证

### 已确认原因与修改

- 新增 test → dev-api 和 `VW_TEST_API_HOST` 覆盖支持。
- 地址优先级：显式 `VW_NOTE_CLEANUP_API_BASE_URL` → 显式 `VW_API_ENV` 对应 host → YAML 地址 → UAT 默认地址。避免显式环境被旧 YAML 固定值忽略。
- README 同步运行方式和优先级。未改变 App 安装包的后端环境。
- 新增 test 映射、独立 host 覆盖、显式环境覆盖旧 YAML、显式 URL 保持最高优先级的回归覆盖。

### 验证

```bash
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest \
apps/velowind-app/appium/tests/unit-test/test_cleanup_config.py \
apps/velowind-app/appium/tests/unit-test/test_note_api_cleanup.py -q
```

- 41 passed，0.09 秒；既有 LibreSSL warning。
- 单元计时目录：`.tmp/appium-ios/runs/20261019-153812-24465/timing/`。
- 真实登录：dev-api 预检通过；真机运行 `20261019-device-test-full-r1` 中图片发布用例 passed（162.48 秒），API 清理步骤 passed（0.6 秒）；完整真机 suite 仍运行中。
- 实际清理核验：POST dev-api `/auth/login/phone/password` 与 DELETE `/posts/pst-55cdebef4d724525807c638671d04aad` 均 HTTP 200 / success；`publish-note-cleanup-result` 为 deleted、skipped=[]，本轮图片笔记无 cleanup-pending。
- 无失败代码尝试；首次组合补丁因用户同期更新 YAML 而匹配失败，确认当前内容后保留用户地址并重新应用。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| 显式选择环境覆盖持久化默认地址 | App 与清理后端切换 | 单元覆盖通过；仍须独立核实已安装 App 的环境 |

## 遗留项与交接

- 真实发布后的清理结果、整套真机结果待运行完成核对，不能以登录通过代替删除成功。

## 第2轮：核对用户链接中的host与缺失附件（2026-10-20）

- 用户报告 `http://127.0.0.1:61209/#suites/a315921332822b24a92de7455c3da80b/c629e7347537652/`；对应运行 `.tmp/appium-ios/runs/20261020-114127-97133/allure-report/`。
- 直接读取该用例报告JSON确认：发布passed，清理broken；`03-cleanup-published-note` 下确有API POST/DELETE子步骤，每项均含 `api-call`、`API request`、`API response` 附件。不是没有采集，需展开嵌套子步骤。
- 两项实际URL均为 `https://dev-api.velowind.com/api/v1/mobile` 开头：与 `VW_API_ENV=test` 的当前映射一致。没有证据需要修改host。
- DELETE目标 `pst-3e7e94cff31b4e4dbf6936178d8488f2` 返回HTTP400、code17210006、messageKey `post.permission.denied`。响应中的当前用户ID匹配消息配置A。登录成功不代表有目标笔记删除权限；实际删除失败，未记录为清理完成。
- 原报告请求附件 `590258cb793e500e.txt`、响应附件 `69b93c98cc69b37e.txt`。诊断只输出方法、URL、HTTP状态及业务错误，不输出登录密码或token。
- 代码核对：清理使用app_config配置登录；会话准备仅在未登录时执行登录，当前代码片段不能证明既有设备用户一定等于清理账号。账号不一致是待核实假设，未确认作者ID。
- 尝试只读查询笔记作者前，dev-api登录预检返回HTTP502，无业务响应；未读取到作者，未重复DELETE、未更换环境或使用管理员绕过作者限制。本轮不修改host或删除断言，未运行发布真机或新增清理。
- 当前状态：host与附件存在已确认；目标笔记清理pending，作者与清理身份对应关系未验证。下一步先核对实际发布账号和目标作者，再决定修复登录前置或清理凭据；不以权限失败推断环境错误。
