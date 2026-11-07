# 2026-10-19 活动搜索测试数据缺失

## 范围与当前状态

- 用例 `test_user_can_search_activities_by_title_or_location`；用户要求整套通过。
- iPhone 17 / App 1.3.0 build 64 / dev-api；最后核实 2026-10-19；当前已调整测试数据，真机待复验。
- 历史索引无本次搜索数据缺失记录。

## 失败证据

- 运行 `20261019-device-test-full-r1`，目录 `.tmp/appium-ios/runs/20261019-device-test-full-r1/`，无临时 URL。
- `05-search-activities-by-keyword` 18.9 秒失败：`Activity search results did not appear for keyword: 张家界`。
- PNG `allure-results/2d7d0ccc-7b8a-466e-8ab1-95facb3008e0-attachment.png`；XML `4489c517-ed8e-4ac1-b16b-bfd141a17825-attachment.xml`。
- 搜索框实际为“张家界”，页面明确“暂无结果 / 没有找到匹配的活动路线。”；没有证据表明此次是结果读取遗漏。
- 当前活动列表可见多条地点“上海市·上海”的活动；此前发布用例在提交前失败，没有创建可供搜索的张家界活动。

## 第 1 轮：修改与验证

- 用例默认关键词改为现有数据地点“上海”，新增 `VW_ACTIVITY_SEARCH_KEYWORD` 覆盖，README 说明可按目标环境准备已有标题或地点。
- 保留通过 UI 输入搜索、等待返回、结果必须包含关键词的断言；不把空结果当作通过，也不自动尝试多个关键词掩盖固定关键词失败。
- 配置常量修改不新增镜像单元；模块已有搜索解析相关单元随 `test_activity_browse_helpers.py` 验证。
- 真机：未复跑，等待当前 suite 结束；只读操作无新增数据或清理。

## 遗留项

- 复跑地点搜索并核对返回数据；需要标题搜索时应提供目标环境已有标题关键词，不能依赖未审核发布数据。
