const evmOpenApi = require('../api/evmOpenApi')
const guildBind = require('../database/guildBind')

/**
 * 修改密码
 */
module.exports = async (ctx, cfg, session, uid, password) => {
  if (!uid || !password) {
    return '请输入用户ID和新密码'
  }

  if (password.length < 6) {
    return '密码长度至少6位'
  }

  // 获取token
  const token = cfg.vtcm_api_token || ''
  
  // 修改密码
  let result = await evmOpenApi.changePassword(ctx.http, uid, password, token)
  if (result.error) {
    return '修改密码失败，请稍后重试'
  }

  return '密码修改成功'
}
