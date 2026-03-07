const BASE_API = 'https://da.vtcm.link'
const OPEN_BASE_API = 'https://open.vtcm.link'

module.exports = {
  /**
   * 查询服务器列表
   */
  async serverList (http) {
    let result = null
    try {
      result = await http.get(`${BASE_API}/server/list`)
    } catch {
      return {
        error: true
      }
    }

    // 拼接返回数据
    let data = {
      error: !result || !result.response || result.response.error
    }
    if (!data.error) {
      data.data = result.response
    }

    return data
  },
  /**
   * 查询在线玩家
   */
  async mapPlayerList(http, serverId, ax, ay, bx, by) {
    let result = null
    try {
      result = await http.get(`${BASE_API}/map/playerList?aAxisX=${ax}&aAxisY=${ay}&bAxisX=${bx}&bAxisY=${by}&serverId=${serverId}`)
    } catch {
      return {
        error: true
      }
    }

    // 拼接返回数据
    let data = {
      error: !result || !result.response || result.response.error
    }
    if (!data.error) {
      data.data = result.response
    }
    return data
  },
  /**
   * 查询玩家信息
   */
  async playerInfo (http, tmpId) {
    let result = null
    try {
      result = await http.get(`${BASE_API}/player/info?tmpId=${tmpId}`)
    } catch {
      return {
        error: true
      }
    }

    // 拼接返回数据
    let data = {
      error: !result || !result.response || result.response.error
    }
    if (!data.error) {
      data.data = result.response
    }
    return data
  },
  /**
   * DLC列表
   */
  async dlcList (http, type) {
    let result = null
    try {
      result = await http.get(`${BASE_API}/dlc/list?type=${type}`)
    } catch(e) {
      return {
        error: true
      }
    }

    // 拼接返回数据
    let data = {
      error: !result || !result.response || result.response.error
    }
    if (!data.error) {
      data.data = result.response
    }
    return data
  },
  /**
   * 玩家里程排行
   */
  async mileageRankingList (http, rankingType, tmpId) {
    let result = null
    try {
      result = await http.get(`${BASE_API}/statistics/mileageRankingList?rankingType=${rankingType}&tmpId=${tmpId || ''}&rankingCount=10`)
    } catch(e) {
      return {
        error: true
      }
    }

    // 拼接返回数据
    let data = {
      error: !result || !result.response || result.response.error
    }
    if (!data.error) {
      data.data = result.response
    }
    return data
  },
  /**
   * 活动列表
   */
  async eventList (http, pageSize = 10, pageNum = 1, eventName = '', beginTime = '', endTime = '', state = '', token = '') {
    let result = null
    try {
      console.log('调用活动列表API:', `${OPEN_BASE_API}/events?pageSize=${pageSize}&pageNum=${pageNum}&eventName=${encodeURIComponent(eventName)}&beginTime=${beginTime}&endTime=${endTime}&state=${state}`)
      result = await http.get(`${OPEN_BASE_API}/events?pageSize=${pageSize}&pageNum=${pageNum}&eventName=${encodeURIComponent(eventName)}&beginTime=${beginTime}&endTime=${endTime}&state=${state}`)
      console.log('API响应:', result)
    } catch(e) {
      console.error('活动列表API错误:', e.message)
      return {
        error: true
      }
    }

    // 拼接返回数据
    let data = {
      error: !result || !result.response || result.response.error
    }
    if (!data.error) {
      data.data = result.response
    }
    return data
  },
  /**
   * 获取成员信息
   */
  async getMember (http, uid = '', tmpId = '', qq = '', token = '') {
    let result = null
    try {
      console.log('调用成员信息API:', `${OPEN_BASE_API}/members/get?uid=${uid}&tmpId=${tmpId}&qq=${qq}`)
      result = await http.get(`${OPEN_BASE_API}/members/get?uid=${uid}&tmpId=${tmpId}&qq=${qq}`)
      console.log('API响应:', result)
    } catch(e) {
      console.error('成员信息API错误:', e.message)
      return {
        error: true
      }
    }

    // 拼接返回数据
    let data = {
      error: !result || !result.response || result.response.error
    }
    if (!data.error) {
      data.data = result.response
    }
    return data
  },
  /**
   * 修改密码
   */
  async changePassword (http, uid, password, token = '') {
    let result = null
    try {
      console.log('调用修改密码API:', `${OPEN_BASE_API}/members/${uid}/password`)
      result = await http.post(`${OPEN_BASE_API}/members/${uid}/password`, { password })
      console.log('API响应:', result)
    } catch(e) {
      console.error('修改密码API错误:', e.message)
      return {
        error: true
      }
    }

    // 拼接返回数据
    let data = {
      error: !result || !result.response || result.response.error
    }
    if (!data.error) {
      data.data = result.response
    }
    return data
  }
}
