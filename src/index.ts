// TMP Bot Plugin for AstrBot
const model = require('./database/model')
const { MileageRankingType } = require('./util/constant')
const tmpQuery = require('./command/tmpQuery/tmpQuery')
const tmpServer = require('./command/tmpServer')
const tmpBind = require('./command/tmpBind')
const tmpTraffic = require('./command/tmpTraffic/tmpTraffic')
const tmpPosition = require('./command/tmpPosition')
const tmpVersion = require('./command/tmpVersion')
const tmpDlcMap = require('./command/tmpDlcMap')
const tmpMileageRanking = require('./command/tmpMileageRanking')

export const name = 'tmp-bot'

/**
 * TMP Bot 插件配置
 */
export interface Config {
  baiduTranslateEnable: boolean;
  baiduTranslateAppId: string;
  baiduTranslateKey: string;
  baiduTranslateCacheEnable: boolean;
  queryShowAvatarEnable: boolean;
  tmpTrafficType: number;
  tmpQueryType: number;
}

/**
 * 插件配置Schema
 */
export const Config = {
  baiduTranslateEnable: {
    type: 'boolean',
    default: false,
    description: '是否启用百度翻译'
  },
  baiduTranslateAppId: {
    type: 'string',
    default: '',
    description: '百度翻译AppID'
  },
  baiduTranslateKey: {
    type: 'string',
    default: '',
    description: '百度翻译密钥'
  },
  baiduTranslateCacheEnable: {
    type: 'boolean',
    default: false,
    description: '是否启用百度翻译缓存'
  },
  queryShowAvatarEnable: {
    type: 'boolean',
    default: false,
    description: '查询结果是否显示头像'
  },
  tmpTrafficType: {
    type: 'number',
    default: 1,
    description: 'TMP交通查询类型'
  },
  tmpQueryType: {
    type: 'number',
    default: 1,
    description: 'TMP查询类型'
  }
}

/**
 * TMP Bot 插件类
 */
export default class TmpBotPlugin {
  ctx: any;
  config: any;

  /**
   * 构造函数
   * @param ctx 上下文对象
   * @param config 配置对象
   */
  constructor(ctx: any, config?: any) {
    this.ctx = ctx;
    this.config = config || {};
    
    // 初始化数据表
    model(this.ctx);
    
    // 注册指令
    this.registerCommands();
  }

  /**
   * 注册命令
   */
  private registerCommands() {
    // 注册各种命令 - 支持带空格和不带空格的查询
    this.ctx.command('tmpquery [tmpId]', async (session: any, tmpId: string) => {
      // 如果没有传入tmpId参数，尝试从消息文本中提取
      if (!tmpId) {
        const messageText = session.content || '';
        const match = messageText.match(/^tmpquery\s*(\d+)$/i);
        if (match) {
          tmpId = match[1];
        }
      }
      return await tmpQuery(this.ctx, this.config, session, tmpId);
    });
    
    this.ctx.command('tmpserverets', async () => {
      return await tmpServer(this.ctx);
    });
    
    this.ctx.command('tmpbind [tmpId]', async (session: any, tmpId: string) => {
      // 如果没有传入tmpId参数，尝试从消息文本中提取
      if (!tmpId) {
        const messageText = session.content || '';
        const match = messageText.match(/^tmpbind\s*(\d+)$/i);
        if (match) {
          tmpId = match[1];
        }
      }
      return await tmpBind(this.ctx, this.config, session, tmpId);
    });
    
    this.ctx.command('tmptraffic [serverName]', async (session: any, serverName: string) => {
      // 如果没有传入serverName参数，尝试从消息文本中提取
      if (!serverName) {
        const messageText = session.content || '';
        const match = messageText.match(/^tmptraffic\s*(.+)$/i);
        if (match) {
          serverName = match[1].trim();
        }
      }
      return await tmpTraffic(this.ctx, this.config, serverName);
    });
    
    this.ctx.command('tmpposition [tmpId]', async (session: any, tmpId: string) => {
      // 如果没有传入tmpId参数，尝试从消息文本中提取
      if (!tmpId) {
        const messageText = session.content || '';
        const match = messageText.match(/^tmpposition\s*(\d+)$/i);
        if (match) {
          tmpId = match[1];
        }
      }
      return await tmpPosition(this.ctx, this.config, session, tmpId);
    });
    
    this.ctx.command('tmpversion', async () => {
      return await tmpVersion(this.ctx);
    });
    
    this.ctx.command('tmpdlcmap', async (session: any) => {
      return await tmpDlcMap(this.ctx, session);
    });
    
    this.ctx.command('tmpmileageranking', async (session: any) => {
      return await tmpMileageRanking(this.ctx, session, MileageRankingType.total);
    });
    
    this.ctx.command('tmptodaymileageranking', async (session: any) => {
      return await tmpMileageRanking(this.ctx, session, MileageRankingType.today);
    });
  }
}
