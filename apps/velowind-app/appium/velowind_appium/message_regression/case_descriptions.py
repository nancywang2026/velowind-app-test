"""Reviewed descriptions for the runnable private-message checks.

Descriptions document intent, not additional executed steps or assertions.
"""

# title, preparation, operations, assertions
PRIVATE_CASES = {
 'private.unread-baseline': ('私信收件方未读基线', '使用独立测试账号C发送、A接收，保留已有会话。', '查询A与C会话的未读数量。', '未读必须为0；存在旧未读则停止，不覆盖原有状态。'),
 'private.send-order-unread': ('连续文字收发与未读累加', '沿用未读为0的会话；生成本轮唯一文本。', 'C向A连续发送3条文字；等待未读累加；从A侧读取包含本轮消息的历史。', 'A未读为3；本轮3条消息内容和接收方向符合发送结果；本子检查未单独断言接收排序。'),
 'private.native-sent-state-and-latest': ('发送状态与重进最新定位', 'C已发送本轮3条消息，A尚未读。', 'C进入A的私信；检查发送状态；返回列表后重新进入会话。', '本轮消息显示已发送或未读；最新消息可见且位于输入框上方，重进后仍定位到最新消息。'),
 'private.read-and-counter': ('阅读后未读归零', 'A有本轮C发来的3条未读消息。', 'A调用会话已读接口；读取标记数量和会话未读返回值。', '标记已读数量为3，会话未读返回0；此项验证接口计数，不代表发件方已读图标已验证。'),
 'private.native-read-icon': ('收件已读后逐条已读显示', 'A已将本轮3条消息标为已读；C登录真机。', '查看C侧会话；返回并重新进入；等待逐条回执刷新。', '本轮3条消息均显示已读；仍显示已发送、未读或缺失回执则失败。'),
 'private.history-recipient-baseline': ('历史定位测试未读基线', 'A发送、C收件；保留已有会话。', '查询C与A会话的未读数量。', '未读为0，避免测试消耗原有未读。'),
 'private.history-scroll-anchor-preparation': ('旧历史稳定锚点准备', 'C登录真机；会话已有可识别的文字历史。', '进入A会话并滚动到旧历史；选择可见且文本唯一的消息；连续采样至位置稳定。', '唯一锚点位于标题与输入框之间；连续位置采样稳定，记录消息ID和Y坐标。'),
 'private.incoming-does-not-pull-old-history': ('浏览旧历史时来信保持位置', '沿用已稳定的旧消息锚点。', 'A发送本轮唯一消息；核对C接收持久化；等待客户端处理后重新读取锚点。', '锚点仍唯一可见，来信前后Y坐标偏移不超过3像素；不放宽阈值。'),
 'private.independent-bottom-baseline': ('连续来信前底部定位准备', 'A发送、C收件；本轮未读基线为0。', '确认真机为C；进入A会话；读取历史最新文字，等待其在底部可见。', '原有未读为0；当前账号正确，最新文字在输入框上方可见。'),
 'private.bottom-delivery-and-unread': ('连续来信内容与自动已读', 'C始终停留在会话底部，A已连续发送本轮3条文字。', '从C侧读取包含本轮3条消息的历史；等待未读查询归零。', '3条消息均为接收方向且内容与发送结果一致；当前会话未读自动变为0。'),
 'private.bottom-follows-newest-incoming': ('返回底部后新来信自动跟随', '旧历史位置检查通过，已有本轮来信。', '滚动回最新消息；A再发送一条唯一消息；保持会话打开并等待。', '新消息自动可见且不被输入框遮挡。'),
}
for index in range(1, 4):
    PRIVATE_CASES[f'private.bottom-follows-incoming-{index}'] = (
        f'底部连续第{index}条来信自动跟随', 'C保持在A会话底部，沿用本轮独立底部准备结果。',
        f'A发送第{index}条唯一文字；不重新进入会话、不手动滚到底部，等待新消息可见。',
        '最新消息自动出现在可视区域，完整位于输入框上方。')


PRIVATE_CASES.update({
 'private.mixed-data-preparation': ('准备私信混合消息及两张不同图片', 'A发送、C接收，C登录真机；保留原会话。', '确认C无旧未读；生成两张本轮独有PNG并分别经私信上传策略直传和回调。', '未读基线0；两份真实上传完成；保存图片供内容与像素核对。'),
 'private.mixed-text-image-send': ('按文字—图片—文字—图片—文字发送', '复用本轮两张上传图片和唯一文字前缀。', '先等待61秒避开前轮频控窗口，再以21秒间隔通过真实私信接口顺序发送5条；图片等待结果确定为SENT；不自动重发未知结果。', '5条发送确认ID唯一；文本回执与内容一致；图片发送成功且发送方内容可用。此项不覆盖App输入框或相册按钮操作。'),
 'private.mixed-both-history-order-and-image-bytes': ('双方历史顺序、内容与图片原文件一致', '沿用本轮5条混合消息ID，C暂不进入会话。', '分别读取A发件和C收件历史；按原返回顺序筛选本轮消息；下载两侧两张图片并比较哈希。', '双方消息ID顺序严格等于发送顺序，类型为文字/图片/文字/图片/文字，方向与文字内容正确；图片可用、assetId及完整字节一致；C未读5。'),
 'private.mixed-native-display-order': ('真机显示混合消息顺序及正确图片', 'C登录真机，本轮5条消息接口核对通过。', 'C进入A会话；读取唯一文本锚点和两张图片区域；采集PNG并逐张对照本轮测试图像素。', '三条文字顺序正确、两张图各位于对应文字之间；排除头像；每张图至少33/36采样点与本轮图片一致，排除空白、占位及错图；末条不被输入框遮挡。'),
 'private.mixed-reentry-display-order': ('重新进入后混合消息顺序与图片保持正确', '沿用C侧本轮混合消息及已有图片，不重复发送。', '返回列表并再次进入同一会话；重新进行文字锚点、图片区域与PNG像素核对。', '重进后5条类型和顺序正确，两张图片仍为本轮图且可见，最新文字不被输入框遮挡。'),
})


def description(name):
    item = PRIVATE_CASES.get(name)
    if not item:
        return None
    title, preparation, operations, assertions = item
    return {'title': title, 'content': title, 'preparation': preparation,
            'operations': operations, 'assertions': assertions}


def render_description(spec):
    return '\n\n'.join(f'**{title}**\n{spec[key]}' for title, key in (
        ('测试内容', 'content'), ('1. 准备数据', 'preparation'),
        ('2. 执行步骤', 'operations'), ('3. 验证点', 'assertions')))
