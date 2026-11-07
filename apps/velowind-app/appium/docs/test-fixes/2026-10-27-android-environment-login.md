# 2026-10-27 Android 环境识别未识别已登录个人页

## 范围与当前状态

- 用户要求：修复 Android 报告失败用例。
- 用例：`tests/message/test_home_video_playback.py::test_four_home_videos_play_normally`，Android 真机 YHK7EERSGAPZX87X / Android 16，实际安装 App 1.2.8 / versionCode 39（adb dumpsys 核实），Appium 4725。preflight 打印的 APK 路径名称不代表实际安装版本。
- 当前状态：235项联合单元通过；第3轮 Android 真机已通过真实环境登录准备，但视频数量1/2失败。另补受控滚动后，r4因设备离线停在preflight，完整播放待恢复后复验。各轮失败保留，未计完整通过。
- 历史参考：[环境登录识别](2026-10-27-app-environment-login.md)、[Android 视频候选](2026-09-15-android-video-candidates.md)、[登录准备失败](2026-10-19-login-session.md)。历史视频识别修复不是本次 setup 失败原因。

## 失败证据

- 用户报告 `http://127.0.0.1:55083/#suites/e2df1617c526fa8fd9b264b94f1409a1/410620b46ea57c1d/`，运行目录 `.tmp/appium-android/runs/20261027-174228-33693/`。
- driver fixture：`Environment login could not identify the Me or login page`，App 环境候选顺序 prod,test；用例正文没有执行。
- 报告截图 `3b486f90468f2ae4.png` / XML `9e578a9550db367e.xml`，调查副本 `/tmp/android-environment-login.{png,xml}`。
- 已确认实际位于已登录“我的”页，resource-id=me-page；“我的笔记 / 个人资料”在 Android 子节点 text 中，父节点 text 为空。原 `_authenticated_me_visible` 只读父 label/text，导致误判。
- 截图有右上角设置齿轮但无 me-settings-button ID；原旧版回退只读 iOS x/y/width/height 与 name=me-page，不能用于 Android bounds/resource-id。右上设置 bounds `[1144,194][1238,289]`；左侧客服 `[1007,194][1101,289]`，页面宽1280。
- 原退出确认后备也仅为 iOS predicate；需要 Android 精确文本、可见性及唯一性校验。此项是代码兼容性缺口，真实确认界面待复验。
- 本次不涉及跨环境 API 核验，不恢复已移除的测试服请求。

## 第 1 轮：修改与验证

- 认证页识别：限定 me-page 可见子树，递归收集可见文字，保留两个认证标记同时出现的要求；排除隐藏祖先/子节点。
- Android 无设置 ID 时，在已验证个人页内按 bounds 及相对页面宽度约束头部方形图标，选唯一最右候选；排除正文、隐藏及页面外节点，使用 Android clickGesture。iOS 原分支保留。
- Android 退出确认识别 text，并只点击唯一可见的“退出登录”；多候选停止，不默认点第一项。优先稳定确认 ID 的原流程保留。
- 新增 Android 子节点、隐藏页/隐藏文本、旧包设置几何及可见退出确认回归。原视频候选与播放断言未修改。
- 单元及目标真机验证运行结果待补；本轮未发布/新增业务数据，清理不涉及。

### 验证进度

```bash
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_environment_login.py apps/velowind-app/appium/tests/unit-test/test_auth.py apps/velowind-app/appium/tests/unit-test/test_session_setup.py -q --tb=short

VW_API_ENV=prod VW_APPIUM_PLATFORM=android VW_ANDROID_TARGET=physical \
VW_ANDROID_UDID=YHK7EERSGAPZX87X VW_APPIUM_SERVER_URL=http://127.0.0.1:4725 \
VW_APPIUM_RUN_ID=20261027-android-environment-login-r1 \
VW_APPIUM_ARTIFACT_DIR=.tmp/appium-android/runs/20261027-android-environment-login-r1/artifacts \
VW_ALLURE_OPEN_PORT=0 pnpm appium:android:test:suite apps/velowind-app/appium/test-suites/android-full.yaml \
-k test_four_home_videos_play_normally --tb=short
```

- 单元 **181 passed / 17.65 秒**，既有 LibreSSL warning；`git diff --check` 通过。
- 对原失败 XML 离线复核：认证页识别 True，设置中心 `(1191,241)`，对应真实截图齿轮。
- 真机前再次检查无设备 pytest；按上面常规 suite 入口定向原用例，preflight passed，运行中。未增加跨环境 API 验证，未调整视频数量或播放断言。

### 第 1 轮实际失败结果

- r1：**1 setup error / 24 deselected / 55.96 秒**。个人页识别、设置及退出均已越过，进入真实 App 密码登录；新错误为 `Login page remained visible after submitting credentials`，未执行视频断言。
- 失败截图 `artifacts/20261027-174706-app-session-setup.png` 及同名 XML。账号密码已输入，页面无明确密码拒绝；协议框为空，登录没有完成。不能将此超时当成账号环境不匹配。
- 确认 `auth._tap_agreement` 稳定 accessibility ID 缺失时仅使用 iOS XPath/predicate，Android 旧包无匹配；协议勾选从未发生。
- 新增数据：无，清理不涉及。第1轮的181单元通过没有覆盖此旧包协议框缺口，不能计为完整真机通过。

## 第 2 轮：Android 协议框兼容

- Android 无 accessibility ID 时，从可见协议文本定位同父级前一个方形复选框，使用 XML bounds 中心点击，避开协议链接；多候选或无法确定则明确失败。
- 旧 RN 复选框没有 checked 语义；对照本地 AgreementCheckbox 源码，选中时才渲染 SVG 勾。用 checkbox 子树内勾标记识别已选，防止模式切换和登录准备重复调用时反向取消。此标记在安装包中的实际勾选后形态待真机确认。
- 原 r1 XML 得到 `(332,1582), checked=False`，与截图空协议框对应。新增已选/未选、隐藏/歧义及幂等回归；iOS 原路径保留。
- 单元及第二轮真机待补；原r1失败保留。

### 第 2 轮验证进度

- 同第1轮单元命令：**185 passed / 17.77 秒**，`git diff --check` 通过。
- 已确认无其他 pytest/run_android_tests，按第1轮真机命令启动 r2（run/artifact ID 改为 `20261027-android-environment-login-r2`）；目前运行中，未提前计通过。设备版本核实为实际1.2.8/code39，未自行安装其他包。

### 第 2 轮实际结果及提交探针

- r2：**1 setup error / 24 deselected / 48.10 秒**，仍是登录页未离开。失败附件 `artifacts/20261027-175103-app-session-setup.{png,xml}`，已能确认协议实际勾选；离线解析 checked=True，与截图和旧包 SVG 标记一致。没有明确密码拒绝，未回退其他环境，视频未执行。
- 此次协议修复有效，但不足以完成登录；不覆盖第2轮失败结果。无新增业务数据。
- 首次独立提交探针创建 driver 后 App 回到根页，没有进入登录页，查找登录文字失败，未执行提交，正常 quit。不能据此判断点击方式。
- 第二次探针先真实打开登录表单并填相同配置凭据：检测到软键盘显示=True，显式 hide_keyboard 后勾选协议，用原生文字 click **一次**；2秒后登录页消失、无拒绝，已成功进入 App。没有执行计划中的后备 clickGesture。证据 `.tmp/appium-android/runs/20261027-android-login-submit-investigation-r2/after.{png,xml}`。
- 已确认隐藏键盘后的单次原生提交成功；原流程没有显式隐藏键盘。键盘使首次外部点击被用于收起/重排页面是当前原因判断，完整用例需下一轮确认，不能用探针替代视频断言。

## 第 3 轮：提交前收起 Android 软键盘

- `_perform_password_login` 在完成密码输入后、定位协议与提交前检查 Android 键盘状态，显示时显式隐藏；iOS 不调用此 API，不增加凭据重复提交。
- 扩展原登录顺序单元，覆盖 iOS 不动键盘、Android 已隐藏不重复隐藏、Android 显示时先隐藏再勾选和提交。既有明确拒绝/超时不混淆及 resubmit=False 断言保留。
- 单元及完整目标真机待补。第1/2轮失败保留，尚不能宣称视频通过。

### 第 3 轮验证进度

- 同单元命令：**187 passed / 17.69 秒**，`git diff --check` 通过。
- 第2次探针最终 XML 有 me-page 和底部导航，登录页不存在，进一步支持单次登录成功；探针没有执行业务发布/新增。
- 前序 pytest/探针均已退出，启动 r3：命令沿用第1轮，run/artifact ID 改为 `20261027-android-environment-login-r3`，完整原目标进行中，不提前计通过。
- r3 已完成环境登录准备、首页准备0.8秒并进入 `02-verify-2-home-videos`，第一个视频 `pst-e6bba5694f2f4c52830634bb86b81947` 播放检查中。未设置 VW_HOME_VIDEO_COUNT，沿用用例默认2个，不将历史函数名 four 解释为本轮验证4个。

### 第 3 轮实际结果：登录修复生效，视频数量另有阻塞

- r3：**1 failed / 24 deselected / 152.04 秒**。环境登录准备成功、首页准备0.8秒 passed；首个视频 `pst-e6bba5694f2f4c52830634bb86b81947` 播放 passed / 20.10秒，完整视频步骤92.9秒 failed：只找到1/2个不同视频。
- 本轮确认个人页/退出、协议勾选与隐藏键盘后的单次登录已在真机完整准备流程生效；没有把准备成功扩大为完整用例通过。
- 后续视频数量问题、21屏截图分析和滚动覆盖验证，追加至 [Android 视频候选记录](2026-09-15-android-video-candidates.md)。当前未修改视频数量或放宽播放断言，未发布/新增业务数据，无清理目标。

## 当前交接：视频漏扫修复已补，设备离线待复验

- 另已补 Android 视频扫描受控滚动；只读探针能用原识别规则发现2个不同视频，详见关联记录第4轮。联合单元235 passed / 18.64秒。
- r4完整复验在preflight被设备离线阻断，无pytest结果。登录准备修复真机已验证；整个原视频目标仍未通过（r3失败保留），修改后两个视频完整播放待设备恢复后确认。
- 无发布/新增业务数据，无清理需求；设备会话/探针均已quit，没有运行中的pytest。未停止任何他人服务。

## 遗留项与交接

- 待完成：单元、Android 真实退出/登录及原视频完整用例；整套未验证。
- 运行前已检查无 pytest/run_android_tests；未停止现有 Appium/报告服务。真机前需再次检查占用。
