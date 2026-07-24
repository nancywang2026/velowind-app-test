# iPhone 手动录制转测试脚本

这套流程用于你在 iPhone 真机上手动操作 App，同时在电脑侧记录步骤，并生成这个仓库可执行的 Appium + pytest 测试草稿。

## 1. 启动录制

先确保 Appium server 已经启动，并且 iPhone 能通过现有 `appium:ios:preflight`。

```bash
pnpm appium:ios:record -- --session-name message-search
```

录制器连上真机后，会先抓一份初始页面状态。之后每当你在手机上完成一个动作，就在终端输入一条命令：

```text
tap <accessibility_id> [text]
tap_text <text>
input <accessibility_id> <value>
back
swipe <up|down>
wait [note]
note <text>
done
```

示例：

```text
action> tap bottom-nav-message 消息
label> open message tab

action> tap search-entry 搜索
label> open search

action> input search-input 长白山
label> type keyword

action> done
```

录制结果会写到：

```text
.tmp/appium-ios/recordings/<session-name>/recording.json
```

同时也会保存每一步的截图和 XML 页面树。

## 2. 生成测试草稿

```bash
pnpm appium:ios:record:generate -- .tmp/appium-ios/recordings/message-search/recording.json
```

默认输出到：

```text
apps/velowind-app/appium/tests/generated/
```

生成后的脚本会：

- 使用现有 `driver / ios_config / step` fixture
- 复用 `tap_accessibility_id_or_text_if_present`、`safe_back`、`swipe_vertical`
- 根据录制时抓到的页面状态，补上 `wait_for_any_accessibility_id_or_text(...)`

## 3. 运行生成稿

```bash
PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/generated/test_message_search.py -q
```

## 说明

这是“半自动生成”而不是完全无脑录制回放：

- 手机上的真实操作由你完成
- 终端里用简短命令描述动作
- 电脑侧自动抓取页面状态并生成 pytest/Appium 草稿

这样生成的代码比纯坐标回放更稳定，也更容易维护。
