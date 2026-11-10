# 2026-11-10 AI 诊断证据与受控补证

## 范围与当前状态

- 用户要求：解决附件只有路径、源码截断、相关历史只有索引、存在疑点就直接转人工四项问题。
- 涉及模块：triage/evidence.py、worker/agent/store/allure_results/CLI，pytest_failure_triage、仓库 agent skill、TRIAGE.md 和示例配置；保留工作区既有改动。
- 最后核实日期：2026-11-10，Asia/Shanghai。
- 当前状态：实现及相关离线回归通过；真实 Codex 历史报告诊断回放与 Allure HTTP 展示已验证；没有真机重跑或业务清理。
- 历史参考：[终端与 Allure](2026-11-07-triage-cli-allure-feedback.md)、[指定影集](2026-11-05-android-requested-photo-album.md)。旧素材/入口结论不能代替本次运行事实。

## 失败证据

- 原运行 `20261110-120049-19391`，job `dbd7b2fadb324223a792def855aa0d02`，报告 `http://127.0.0.1:49750/#suites/a315921332822b24a92de7455c3da80b/49b02b3717c3599d/`。
- 原错误 `Photo selection did not complete`，Android 16 真机，图片笔记发布步骤失败。原 failed、步骤、时间和附件保持。
- 旧诊断未收到图像/XML内容、关键选图函数和 photo_picker 依赖，相关历史正文缺失。旧 worker 对 uncertainties 非空一律 needs_human。
- 原截图和 XML 显示前台 com.android.photopicker，影集已选中，仅见相机和屏幕截图，选中数 0；不能据此推断其他入口/素材索引状态。

## 第 1 轮：实现与初步验证

### 修改

- 会话开始保存白名单自动化源码、测试数据和历史的脱敏快照及原始/脱敏 hash；失败时检测版本/内容漂移。没有快照的旧 dirty 任务明确 unavailable，不用 HEAD 伪装运行源码。单文件/总量超限显式记录。
- 从内层堆栈提取完整 AST 函数，追踪两层直接依赖，保留常量、导入、路径/行号/版本/hash。内容预算不足整项缺失，不截断函数。
- XML 自动读取并脱敏，保留父子结构/选中/坐标；较大树优先目标与选中节点、祖先/邻近节点并报告遗漏数量。已本地审查、哈希匹配且有效 PNG 才作为实际图像输入；其他情况明确 unavailable，可继续依据 XML 诊断。
- 匹配 testdata YAML 与相关历史正文；当前历史只作为标注版本的补充证据。
- v2 schema 增加候选原因、建议、结构化阻断/非阻断疑点和补证请求。旧字符串疑点仍阻断；非阻断项不再一律转人工。repair/review 同步应用阻断判断。
- 补证只读本任务附件和白名单源码/历史/测试数据，检查解析后的路径、版本、任务归属和预算。默认两轮、每轮六项，重复/越界/无新内容有明确停止原因；不运行 shell、不操作设备。
- 逐轮保存上下文、实际 prompt、模型答案和处理状态。CLI 输出轮次，Allure 显示候选原因、建议、轮次/停止原因且保留原结果。
- 增加 resume --diagnose-only：仅诊断和报告写回，避免进入修复、真机和外部建单。

### 失败尝试与复验

- 第一轮：42 passed / 2 failed。补证测试请求的 locate 已在初始依赖中自动供应，正确触发“重复请求无新信息”；改用初始未读取的 verify 函数，继续验证补证链路。
- 第二轮：43 passed / 1 failed。测试直接匹配 JSON 序列化字符串中的引号，改为解析 JSON 后检查 content。
- 第三轮：45 passed。新增测试覆盖后，扩展回归 138 passed / 1 failed：较大 XML 的同级节点排序使末尾 selected 目标被预算排除。已修正为先选目标本身，再祖先/同级及其他节点，保留该失败记录。
- 修正后扩展回归：139 passed，25.00 秒（1 项既有 urllib3/LibreSSL 警告）。报告 `.tmp/appium-ios/runs/20261110-134542-32082/timing/`；目录含 ios 仅是单元测试框架默认名，不是真机验证。

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest -q \
  apps/velowind-app/appium/tests/unit-test/test_triage_evidence.py \
  apps/velowind-app/appium/tests/unit-test/test_failure_triage.py \
  apps/velowind-app/appium/tests/unit-test/test_triage_allure_results.py \
  apps/velowind-app/appium/tests/unit-test/test_triage_startup.py \
  apps/velowind-app/appium/tests/unit-test/test_session_setup.py \
  apps/velowind-app/appium/tests/unit-test/test_timing_report.py \
  apps/velowind-app/appium/tests/unit-test/test_cleanup_report.py
```

## 第 2 轮：真实 Codex 历史报告回放

- 本地审查原失败截图后，记录诊断专用历史截图 review，不伪称当前手机截图；未设置可用于 Bug 上传的当前设备状态。
- Worker.process(resume=True, rediagnose=True, diagnose_only=True) 使用新协议调用真实 Codex，随后回写原 Allure。未执行 repair/bug 路由。
- 实际模型读到 PNG、XML、相关历史全文并引用证据 ID；确认“选图器已打开”“影集选中”“零选图”“当前页无长白山”，不再把相册未打开当作同等候选。
- 模型将未知 App 版本/清理标为非阻断，输出三个候选原因及具体建议：记录实际参数/选图路径、核实相册入口/素材索引、保留指定素材要求、不退回相机第一张、不放宽断言。
- 原任务仍 unknown/manual、needs_human：旧 dirty 运行无源码快照及实际解析参数，本次其他入口/素材索引也无只读历史证据；模型明确说明这些实质限制，没有编造补丁。此次没有发生补证轮次；自动补证链路由确定性离线测试验证，不能声称本历史任务真实补证两轮通过。
- HTTP 实读原 UID 路径仍可用，原状态 failed；旧诊断附件保留，新增一版文本/JSON。原 Allure 服务未终止。

## 可复用方法与边界

- 历史回放与新在线运行分开：新快照不能追溯还原旧 dirty 源码。
- 路径不是内容；模型图像输入必须来自通过审查和哈希核对的 PNG。
- 补证预算耗尽或需要设备动作时，提供明确下一步，不能通过删除疑点或放宽断言制造成功。
- 不改变原断言、清理、设备验证结果；未创建 Taiga Bug、未提交/推送代码。

## 遗留项与交接

- 真机完整发布、实际素材身份、发布后校验和清理：本轮未验证。
- 历史任务仍需受控现场取证；不得把当前历史文档当作原运行源码。
- 诊断快照支持 dirty 分析，现有自动修补仍要求可还原的干净 commit；未扩展业务代码修改范围。
- XML 脱敏依赖属性/控件规则与模式，并非通用隐私分类器；未经审查的 PNG 不自动传输。


### 最终复验与运行服务加载

- 清理显式 rediagnose 的旧补证停止原因，新增回归验证不会继承过期的“预算耗尽”提示。最终四个核心文件复验 **48 passed / 8.49秒**；报告 `.tmp/appium-ios/runs/20261110-134626-33583/timing/`。此前扩展139项通过保持；最终48项包含新增状态回归，不把两次数量相加当作全套。
- `git diff --check` 通过；新增文件经 compileall 及 pytest 导入验证。
- 核对原 watch 的 PID、完整启动命令、队列和任务状态，并在获得 worker 任务锁且所有任务均终态后发送 SIGINT 退出空闲旧 watcher；未终止 Appium、Allure 或设备测试。
- 通过 ensure_worker 启动新进程，确认 watch 生存期锁已持有，新流程已加载。未新增系统开机自启。
