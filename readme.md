# astrbot-plugin-tmp-bot

[![npm](https://img.shields.io/npm/v/koishi-plugin-tmp-bot?style=flat-square)](https://github.com/BGYdook/astrbot-plugin-tmp-bot)

欧洲卡车模拟2 TMP 查询机器人，用于查询玩家信息、位置、服务器路况及排行榜等。

### 指令一览
| 指令 | 功能 | 示例 |
|------|------|------|
| tmpbind / 绑定 | 绑定 TMP ID，绑定后其他指令可省略 ID | tmpbind 123 |
| tmpquery / 查询 | 查询 TMP 玩家信息 | tmpquery 123 |
| tmpposition / 定位 | 查询玩家位置信息 | tmpposition 123 |
| tmptraffic / 服务器 | 查询服务器热门地点路况（支持服务器简称：s1、s2、p、a） | tmptraffic s1 |
| tmpserverats | 查询美卡服务器信息列表 | tmpserverats |
| tmpserverets | 查询欧卡服务器信息列表 | tmpserverets |
| tmpversion | 查询插件/接口版本信息 | tmpversion |
| tmpdlcmap / 地图DLC | 列出地图相关 DLC | tmpdlcmap |
| tmpmileageranking | 总里程排行榜（自 2025-08-23 20:00 起统计，绑定后可查看个人排名） | tmpmileageranking |
| tmptodaymileageranking | 今日里程排行榜（每日 0 点重置，绑定后可查看个人排名） | tmptodaymileageranking |

### 接口与数据
API 文档与数据来源：https://apifox.com/apidoc/shared/38508a88-5ff4-4b29-b724-41f9d3d3336a