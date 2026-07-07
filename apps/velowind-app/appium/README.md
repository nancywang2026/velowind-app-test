# iOS Appium 真机功能遍历

这套脚本用于在 iOS 真机上通过 Appium + Python 遍历寻风集 Taro RN App 的主要功能入口。第一版聚焦功能巡检：启动 App、处理常见系统弹窗、切换底部 Tab、尝试城市/日期/搜索等可见入口，并在失败时保存截图和页面 XML。

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
python3 -m pytest apps/velowind-app/appium/tests/test_ios_feature_walkthrough.py -q
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

用例运行结束后会自动生成并打开 Allure HTML 报告；如果本机还没有 `allure` 命令，先执行 `brew install allure`。

如果 WebDriverAgent 已经成功安装并验证过，日常调试可跳过 WDA build 预检以减少启动时间：

```bash
export VW_IOS_SKIP_WDA_PREFLIGHT=true
pnpm appium:ios:test
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
| `VW_IOS_SKIP_WDA_PREFLIGHT` | `false` | 是否跳过 preflight 阶段的 WDA build 检查 |
| `VW_IOS_USE_NEW_WDA` | `false` | 是否每次重装 WebDriverAgent |
| `VW_IOS_NO_RESET` | `true` | 是否保留 App 状态 |
