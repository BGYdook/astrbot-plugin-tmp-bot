const truckersMpApi = require('../api/truckersMpApi')
const evmOpenApi = require('../api/evmOpenApi')

module.exports = async (ctx) => {
  // 查询服务器信息
  let serverData = await evmOpenApi.serverList(ctx.http)
  if (serverData.error) {
    return '查询服务器失败，请稍后重试'
  }

  // 构建消息
  let message = ''
  // 收集每个服务器的显示块，最后再用双换行拼接，避免多余空行
  let blocks = []
  for (let server of serverData.data) {
    // 忽略特定服务器（例如: Simulation, [US] Simulation, [US] Arcade）
    const serverName = server.serverName ? server.serverName.trim() : ''
    const ignoreServers = ['Simulation', '[US] Simulation', '[US] Arcade']
    if (ignoreServers.includes(serverName)) {
      continue
    }

    let block = ''
    block += '服务器: ' + ( server.isOnline === 1 ? '🟢' : '⚫' ) + server.serverName
    block += `\n玩家人数: ${server.playerCount}/${server.maxPlayer}`
    if (server.queue) {
      block += ` (队列: ${server.queueCount})`
    }
    // 服务器特性
    let characteristicList = []
    if (!(server.afkEnable === 1)) {
      characteristicList.push('⏱挂机')
    }
    if (server.collisionsEnable === 1) {
      characteristicList.push('💥碰撞')
    }
    if (characteristicList && characteristicList.length > 0) {
      block += '\n服务器特性: ' + characteristicList.join(' ')
    }

    blocks.push(block)
  }

  message = blocks.join('\n\n')

  return message
}
