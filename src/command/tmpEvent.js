const evmOpenApi = require('../api/evmOpenApi')

/**
 * 活动列表
 */
module.exports = async (ctx, cfg, pageSize = 3, pageNum = 1, eventName = '', beginTime = '', endTime = '', state = '') => {
  // 获取token
  const token = cfg.vtcm_api_token || ''
  
  // 查询活动列表
  let eventData = await evmOpenApi.eventList(ctx.http, pageSize, pageNum, eventName, beginTime, endTime, state, token)
  if (eventData.error) {
    return '查询活动列表失败，请稍后重试'
  }

  // 构建消息
  let message = ''
  message += `活动总数: ${eventData.data.total}\n\n`
  
  for (let event of eventData.data.rows) {
    // 如果前面有内容，换行
    if (message && !message.endsWith('\n\n')) {
      message += '\n\n'
    }

    message += `📅活动名称: ${event.eventName}`
    message += `\n🕐开始时间: ${event.startTime}`
    message += `\n🕐结束时间: ${event.endTime}`
    message += `\n📋状态: ${event.state === 1 ? '未开始' : event.state === 2 ? '进行中' : '已结束'}`
    if (event.serverName) {
      message += `\n🖥服务器: ${event.serverName}`
    }
    if (event.autoCheckInEnable === 1) {
      message += '\n🔄自动签到: 启用'
    }
  }
  
  if (eventData.data.rows.length === 0) {
    message += '暂无活动数据'
  }
  
  return message
}
