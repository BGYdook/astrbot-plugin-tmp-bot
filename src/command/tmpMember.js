const evmOpenApi = require('../api/evmOpenApi')
const guildBind = require('../database/guildBind')

/**
 * 获取成员信息
 */
module.exports = async (ctx, cfg, session, uid = '', tmpId = '', qq = '') => {
  // 如果没有传入参数，尝试从数据库查询绑定信息
  if (!uid && !tmpId && !qq) {
    let guildBindData = await guildBind.get(ctx.database, session.platform, session.userId)
    if (!guildBindData) {
      return '请输入查询参数 (uid/tmpId/qq)'
    }
    tmpId = guildBindData.tmp_id
  }

  // 获取token
  const token = cfg.vtcm_api_token || ''
  
  // 查询成员信息
  let memberData = await evmOpenApi.getMember(ctx.http, uid, tmpId, qq, token)
  if (memberData.error) {
    return '查询成员信息失败，请稍后重试'
  }

  // 构建消息
  let message = ''
  message += `🆔用户ID: ${memberData.data.uid}`
  message += `\n🎮TMP ID: ${memberData.data.tmpId}`
  message += `\n😀TMP名称: ${memberData.data.tmpName}`
  message += `\n👔TMP角色: ${memberData.data.tmpRole}`
  message += `\n🚚车队编号: ${memberData.data.teamNumber}`
  message += `\n🔗Steam ID: ${memberData.data.steamId}`
  message += `\n💬QQ: ${memberData.data.qq}`
  message += `\n📧邮箱: ${memberData.data.email}`
  message += `\n📅加入日期: ${memberData.data.joinDate}`
  if (memberData.data.quitDate) {
    message += `\n📅退出日期: ${memberData.data.quitDate}`
  }
  message += `\n📋状态: ${memberData.data.state === 1 ? '正常' : '异常'}`
  message += `\n🏆积分: ${memberData.data.point}`
  
  return message
}
