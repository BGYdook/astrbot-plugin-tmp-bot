"""
菜单帮助功能
"""


async def tmphelp(self, event):
    help_text = """TMP查询插件使用说明

可用命令:
1. 绑定 [TMP ID]
2. 查询 [TMP ID]
3. 定位 [TMP ID]
4. 地图DLC
5. 总里程排行
6. 今日里程排行
7. 足迹 [服务器简称] [TMP ID]
8. 路况[s1/s2/p/a]
9. 解绑
10. 服务器
11. 插件版本
12. 菜单
使用提示: 绑定后可直接发送 查询/定位/足迹 [服务器简称]
"""
    yield event.plain_result(help_text)
