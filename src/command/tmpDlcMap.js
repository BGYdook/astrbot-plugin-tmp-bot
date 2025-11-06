const { resolve } = require('path')
const common = require('../util/common')
const evmOpenApi = require('../api/evmOpenApi')

module.exports = async (ctx, session) => {
  if (!ctx.puppeteer) {
    return '未启用 Puppeteer 功能'
  }

  // 查询DLC数据
  let dlcData = await evmOpenApi.dlcList(ctx.http, 1)

  let page
  try {
    page = await ctx.puppeteer.page()
    await page.setViewport({ width: 1000, height: 1000 })
    await page.goto(`file:///${resolve(__dirname, '../resource/dlc.html')}`)
    await page.evaluate(`setData(${JSON.stringify(dlcData.data)})`)
    await page.waitForNetworkIdle()
    await common.sleep(500)
    const element = await page.$("#dlc-info-container");
    const imageBuffer = await element.screenshot({
      encoding: 'binary'
    })
    const base64 = Buffer.from(imageBuffer).toString('base64')
    return `[CQ:image,file=base64://${base64}]`
  } catch (e) {
    console.info(e)
    return '渲染异常，请重试'
  } finally {
    if (page) {
      await page.close()
    }
  }
}
