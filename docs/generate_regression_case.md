现在实现Activity 模块，应该在一个单独的package: Activity, 
实现功能：
发布活动功能： 进入App 首页 点击下方➕ ，
选择发布类型：活动，填写所有信息，最后提交审核，


开发自动化测试脚本：
1，IOS和Android使用同一套业务测试代码。
2.生成代码时要考虑IOS和Android兼容性
3. 使用AccessibilityId,避免使用耗时的XPath
4. 实现功能后，使用真机和模拟器跑用例来验证

代码完成后：
1. 在真机上测试，保证测试通过，
2. Allure report 可以弹出，里面包含截图信息，以及验证点