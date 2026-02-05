"""
服务器与版本查询功能
"""


async def tmpserver(self, event):
    if not self.session:
        yield event.plain_result("插件初始化中，请稍后重试")
        return

    try:
        url = "https://api.truckersmp.com/v2/servers"
        async with self.session.get(url, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                code = data.get("code") if isinstance(data, dict) else None
                if code is not None and int(code) != 200:
                    yield event.plain_result("查询服务器失败，请稍后重试")
                    return
                servers = data.get("data") or data.get("response") or data.get("result") or []
                if not isinstance(servers, list):
                    yield event.plain_result("查询服务器失败，请稍后重试")
                    return
                message = ""
                for server in servers:
                    if message:
                        message += "\n\n"
                    is_online = server.get("isOnline")
                    if is_online is None:
                        is_online = server.get("online")
                    online_flag = int(is_online) == 1 if isinstance(is_online, (int, float, str)) else bool(is_online)
                    name = server.get("serverName") or server.get("name") or "未知服务器"
                    status = "🟢" if online_flag else "⚫"
                    message += f"服务器: {status}{name}"
                    players = server.get("playerCount")
                    if players is None:
                        players = server.get("players", 0)
                    max_players = server.get("maxPlayer")
                    if max_players is None:
                        max_players = server.get("maxplayers", 0)
                    message += f"\n玩家人数: {players}/{max_players}"
                    queue_flag = server.get("queue", 0)
                    queue_count = server.get("queueCount", queue_flag)
                    if queue_flag:
                        message += f" (队列: {queue_count})"
                    characteristic_list = []
                    afk_enable = server.get("afkEnable")
                    if afk_enable is None:
                        afk_enable = server.get("afkEnabled")
                    if afk_enable is None:
                        afk_enable = server.get("afkenable")
                    if afk_enable is None:
                        afk_enable = server.get("afkenabled")
                    can_afk = False
                    if isinstance(afk_enable, bool):
                        can_afk = afk_enable
                    elif isinstance(afk_enable, (int, float)):
                        can_afk = int(afk_enable) == 1
                    elif isinstance(afk_enable, str):
                        can_afk = afk_enable.strip().lower() in ("1", "true", "yes", "y")
                    if not can_afk:
                        characteristic_list.append("⏱挂机")
                    collisions_enable = server.get("collisionsEnable")
                    if collisions_enable is None:
                        collisions_enable = server.get("collisions")
                    if isinstance(collisions_enable, bool):
                        if collisions_enable:
                            characteristic_list.append("💥碰撞")
                    elif isinstance(collisions_enable, (int, float)):
                        if int(collisions_enable) == 1:
                            characteristic_list.append("💥碰撞")
                    if characteristic_list:
                        message += "\n服务器特性: " + " ".join(characteristic_list)
                yield event.plain_result(message or "暂无在线服务器")
            else:
                yield event.plain_result(f"查询服务器状态失败，API返回错误状态码: {response.status}")
    except Exception:
        yield event.plain_result("网络请求失败，请检查网络或稍后重试。")


async def tmpversion(self, event):
    if not self.session:
        yield event.plain_result("插件初始化中，请稍后重试")
        return

    try:
        url = "https://api.truckersmp.com/v2/version"
        async with self.session.get(url, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                plugin_ver = data.get("name") or data.get("version") or "未知"
                ets2_ver = data.get("supported_game_version") or data.get("supported_ets2_version") or "未知"
                ats_ver = data.get("supported_ats_game_version") or data.get("supported_ats_version") or "未知"
                protocol = data.get("protocol") or "未知"

                message = "TMP 插件版本信息\n" + "=" * 18 + "\n"
                message += f"TMP 插件版本: {plugin_ver}\n"
                message += f"欧卡支持版本: {ets2_ver}\n"
                message += f"美卡支持版本: {ats_ver}"
                yield event.plain_result(message)
            else:
                yield event.plain_result(f"查询版本信息失败，API返回错误状态码: {response.status}")
    except Exception:
        yield event.plain_result("查询版本信息失败，请稍后重试。")
