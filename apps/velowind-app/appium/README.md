# iOS Appium 真机功能遍历

这套脚本用于在 iOS 真机上通过 Appium + Python 遍历寻风集 Taro RN App 的主要功能入口。当前用例按功能模块组织：`tests/smoke/` 放快速巡检，`tests/message/` 放消息/资讯浏览流程；失败时会保存截图和页面 XML。

同一套 Appium + pytest 骨架也支持 Android 本地模拟器，Android 用例和报告独立写入 `.tmp/appium-android/`。

## 环境准备

```bash
npm install -g appium
appium driver install xcuitest
python3 -m pip install -r apps/velowind-app/appium/requirements.txt
```

如需生成 Allure HTML 报告，需要额外安装 Allure CLI：

```bash
brew install allure
```

确认 Appium 与 XCUITest driver：

```bash
appium --version
appium driver list --installed
```

## Android 本地模拟器

安装 Android driver：

```bash
npm install -g appium
appium driver install uiautomator2
python3 -m pip install -r apps/velowind-app/appium/requirements.txt
```

启动一个本地模拟器并确认在线：

```bash
emulator -list-avds
emulator -avd <AVD_NAME>
adb devices
```

启动 Appium server：

```bash
appium --log-timestamp
```

配置 APK 或已安装 App：

```bash
export VW_ANDROID_UDID=emulator-5554
export VW_ANDROID_APP=/absolute/path/to/velowind.apk
export VW_ANDROID_APP_PACKAGE=com.velowind.rider
```

如果不传 `VW_ANDROID_APP`，框架会启动模拟器上已经安装的 App，此时必须提供 activity：

```bash
export VW_ANDROID_APP_PACKAGE=com.velowind.rider
export VW_ANDROID_APP_ACTIVITY=.MainActivity
```

如果不确定 activity，可先启动 App 后查看：

```bash
adb shell monkey -p com.velowind.rider 1
adb shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'
```

运行 Android 预检和 smoke：

```bash
pnpm appium:android:preflight
pnpm appium:android:test
```

按 suite 文件运行：

```bash
pnpm appium:android:test:suite apps/velowind-app/appium/test-suites/android-smoke.yaml
```

Android 失败调试产物会写入：

```text
.tmp/appium-android/
```

Android 常用环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VW_APPIUM_SERVER_URL` | `http://127.0.0.1:4723` | Appium server 地址 |
| `VW_ANDROID_UDID` | 自动发现在线 emulator | Android 模拟器 UDID |
| `VW_ANDROID_DEVICE_NAME` | `Android Emulator` | Appium deviceName |
| `VW_ANDROID_APP` | 空 | 指向 `.apk` 文件时，Appium 会安装并启动 |
| `VW_ANDROID_APP_PACKAGE` | `com.velowind.rider` | Android package |
| `VW_ANDROID_APP_ACTIVITY` | 空 | 未传 APK 时必填 |
| `VW_ANDROID_NO_RESET` | `true` | 是否保留 App 状态 |
| `VW_ANDROID_AUTO_GRANT_PERMISSIONS` | `true` | 是否自动授予权限 |
| `VW_APPIUM_ARTIFACT_DIR` | `.tmp/appium-android` | 截图和 XML 输出目录 |

确认真机 UDID：

```bash
xcrun xctrace list devices
```

推荐先确认当前在线真机：

```bash
pnpm appium:ios:preflight
```

如果机器同时连接多台 iOS 设备，可显式指定：

```bash
export VW_IOS_UDID=<你的真机 UDID>
```

默认 Bundle ID：

```bash
export VW_IOS_BUNDLE_ID=com.velowind.rider
```

如果 WebDriverAgent 签名失败，配置 Apple Team 和独立 WDA bundle id：

```bash
export VW_IOS_XCODE_ORG_ID=K2VHBX5KLX
export VW_IOS_XCODE_SIGNING_ID="Apple Development"
export VW_IOS_UPDATED_WDA_BUNDLE_ID=com.velowind.rider.WebDriverAgentRunner
export VW_IOS_ALLOW_PROVISIONING_DEVICE_REGISTRATION=true
export VW_IOS_SHOW_XCODE_LOG=true
```

## 运行

先启动 Appium server：

```bash
appium --log-timestamp
```

另开一个终端运行：

```bash
python3 -m pytest apps/velowind-app/appium/tests/smoke/test_ios_feature_walkthrough.py -q
```

也可以使用仓库脚本：

```bash
cd /Users/test/Documents/velowind-app-dev-test
pnpm appium:ios:test
```

默认 `appium:ios:test` 只运行快速 smoke 用例，适合日常调试。完整功能遍历使用：

```bash
pnpm appium:ios:test:full
```

如果希望像 `testng.xml` 一样按配置指定本次要跑的用例，可以传入 suite 文件：

```bash
pnpm appium:ios:test:suite apps/velowind-app/appium/test-suites/message-publish.yaml
```

也可以直接调用运行器：

```bash
PYTHONPATH=apps/velowind-app/appium python3 -m velowind_appium.run_ios_tests --suite apps/velowind-app/appium/test-suites/smoke.yaml
```

suite 文件支持三类字段：

```yaml
tests:
  - smoke/test_ios_feature_walkthrough.py
  - message/test_ios_publish_note.py
markers:
  - smoke
pytest_args:
  - --maxfail=1
```

- `tests`：相对 `apps/velowind-app/appium/tests/` 的测试文件路径
- `markers`：会拼成 `pytest -m "marker1 or marker2"`
- `pytest_args`：补充透传给 pytest 的额外参数

消息模块单独运行：

```bash
PYTHONPATH=apps/velowind-app/appium python3 -m pytest apps/velowind-app/appium/tests/message/test_ios_message_browse.py -q -m full
```

用例运行结束后会自动生成并打开 Allure HTML 报告；如果本机还没有 `allure` 命令，先执行 `brew install allure`。

WebDriverAgent 默认复用已安装版本，不会在每次运行前执行 WDA build 预检。若需要显式验证 WDA 签名，可开启预检：

```bash
export VW_IOS_SKIP_WDA_PREFLIGHT=false
pnpm appium:ios:test
```

如果你是从 PyCharm 直接运行 pytest，用例默认不会在会话结束时自动打开 Allure 报告；如需恢复该行为，可显式设置：

```bash
export VW_APPIUM_AUTO_OPEN_REPORT=true
```

失败时调试产物会写入：
    
```text
.tmp/appium-ios/
```

## Allure 报告

测试运行后会自动生成 Allure raw results：

```text
.tmp/appium-ios/allure-results/
```

生成 HTML 报告：

```bash
pnpm appium:ios:allure:generate
```

打开报告：

```bash
pnpm appium:ios:allure:open
```

失败用例会把截图和页面 XML 作为附件写入报告。
功能遍历用例会在首页、底部 Tab、返回首页和已进入的功能入口处主动截图；截图会同时保存到 `.tmp/appium-ios/` 并附加到 Allure 报告。

## 用例分包

```text
apps/velowind-app/appium/tests/
├── smoke/    # 首页与底部 Tab 的快速巡检
└── message/  # 普通用户浏览消息详情、留言、图票文案切换
```

内置 suite 示例位于：

```text
apps/velowind-app/appium/test-suites/
```

## 常用环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VW_APPIUM_SERVER_URL` | `http://127.0.0.1:4723` | Appium server 地址 |
| `VW_IOS_UDID` | 自动发现在线 iPhone | iOS 真机 UDID |
| `VW_IOS_BUNDLE_ID` | `com.velowind.rider` | 已安装 App 的 Bundle ID |
| `VW_IOS_APP` | 空 | 指向 `.app` 文件时，Appium 会先安装再启动 |
| `VW_APPIUM_ARTIFACT_DIR` | `.tmp/appium-ios` | 截图和 XML 输出目录 |
| `VW_IOS_XCODE_ORG_ID` | 空 | WebDriverAgent 签名用 Apple Team ID |
| `VW_IOS_XCODE_SIGNING_ID` | Appium 默认值 | WebDriverAgent 签名证书名，真机常用 `Apple Development` |
| `VW_IOS_UPDATED_WDA_BUNDLE_ID` | 空 | 独立 WebDriverAgent Runner Bundle ID |
| `VW_IOS_ALLOW_PROVISIONING_DEVICE_REGISTRATION` | `false` | 是否允许 Xcode 自动更新 provisioning 并注册设备 |
| `VW_IOS_SHOW_XCODE_LOG` | `false` | 是否在 Appium 日志中输出 Xcode build 日志 |
| `VW_IOS_SKIP_WDA_PREFLIGHT` | `true` | 是否跳过 preflight 阶段的 WDA build 检查；设为 `false` 可显式验证 WDA 签名 |
| `VW_IOS_USE_NEW_WDA` | `false` | 是否每次重装 WebDriverAgent |
| `VW_IOS_NO_RESET` | `true` | 是否保留 App 状态 |
