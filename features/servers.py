"""TruckersMP server status for ETS2 and ATS."""

from typing import Optional

from .shared import read_json
from .astrbot_compat import AstrMessageEvent


class ServersMixin:
    async def tmpserver(self, event: AstrMessageEvent, game_filter: Optional[str] = None):
        """[命令: 服务器] 查询TruckersMP官方服务器的实时状态。"""
        if not self.session:
            yield event.plain_result("插件初始化中，请稍后重试")
            return

        try:
            url = "https://api.truckersmp.com/v2/servers"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await read_json(response)
                    code = data.get('code') if isinstance(data, dict) else None
                    if code is not None and int(code) != 200:
                        yield event.plain_result("查询服务器失败，请稍后重试")
                        return
                    servers = data.get('data') or data.get('response') or data.get('result') or []
                    if not isinstance(servers, list):
                        yield event.plain_result("查询服务器失败，请稍后重试")
                        return
                    game_filter = str(game_filter or '').strip().lower()
                    heading = "美卡服务器状态" if game_filter == 'ats' else None
                    # 先收集每个服务器的文本块，避免循环内以条件追加换行导致出现多余空行
                    blocks = []
                    for server in servers:
                        game_name = str(
                            server.get('game')
                            or server.get('gameName')
                            or server.get('game_name')
                            or ''
                        ).strip().upper()
                        name_value = server.get('serverName') or server.get('name') or '未知服务器'
                        try:
                            name_trim = name_value.strip() if isinstance(name_value, str) else str(name_value)
                        except Exception:
                            name_trim = str(name_value)
                        if game_filter == 'ats':
                            if game_name:
                                if game_name != 'ATS':
                                    continue
                            elif not name_trim.upper().startswith('[US]'):
                                continue
                        elif game_filter == 'ets':
                            if game_name:
                                if game_name != 'ETS2':
                                    continue
                            elif name_trim.upper().startswith('[US]'):
                                continue

                        is_online = server.get('isOnline')
                        if is_online is None:
                            is_online = server.get('online')
                        online_flag = int(is_online) == 1 if isinstance(is_online, (int, float, str)) else bool(is_online)

                        # 兼容性：优先使用 serverName，再 fallback 到 name
                        name = name_value
                        # 忽略特定服务器（保持服务器名称的精确匹配行为）
                        ignore_servers = ['Simulation', '[US] Simulation', '[US] Arcade']
                        if game_filter != 'ats' and name_trim in ignore_servers:
                            continue

                        status = "🟢" if online_flag else "⚫"
                        block = f"服务器: {status}{name}"

                        players = server.get('playerCount')
                        if players is None:
                            players = server.get('players', 0)
                        max_players = server.get('maxPlayer')
                        if max_players is None:
                            max_players = server.get('maxplayers', 0)
                        block += f"\n玩家人数: {players}/{max_players}"

                        queue_flag = server.get('queue', 0)
                        queue_count = server.get('queueCount', queue_flag)
                        if queue_flag:
                            block += f" (队列: {queue_count})"

                        characteristic_list = []
                        afk_enable = server.get('afkEnable')
                        if afk_enable is None:
                            afk_enable = server.get('afkEnabled')
                        if afk_enable is None:
                            afk_enable = server.get('afkenable')
                        if afk_enable is None:
                            afk_enable = server.get('afkenabled')
                        can_afk = False
                        if isinstance(afk_enable, bool):
                            can_afk = afk_enable
                        elif isinstance(afk_enable, (int, float)):
                            can_afk = int(afk_enable) == 1
                        elif isinstance(afk_enable, str):
                            can_afk = afk_enable.strip().lower() in ("1", "true", "yes", "y")
                        if not can_afk:
                            characteristic_list.append("⏱挂机")

                        collisions_enable = server.get('collisionsEnable')
                        if collisions_enable is None:
                            collisions_enable = server.get('collisions')
                        if isinstance(collisions_enable, bool):
                            if collisions_enable:
                                characteristic_list.append("💥碰撞")
                        elif isinstance(collisions_enable, (int, float)):
                            if int(collisions_enable) == 1:
                                characteristic_list.append("💥碰撞")

                        if characteristic_list:
                            block += "\n服务器特性: " + " ".join(characteristic_list)

                        blocks.append(block)

                    message = "\n\n".join(blocks)
                    if heading:
                        message = f"{heading}\n{'=' * 18}\n\n{message}" if message else "暂无美卡服务器数据"
                    yield event.plain_result(message or "暂无在线服务器")
                else:
                    yield event.plain_result(f"查询服务器状态失败，API返回错误状态码: {response.status}")
        except Exception:
            yield event.plain_result("网络请求失败，请检查网络或稍后重试。")

    async def tmpats_server(self, event: AstrMessageEvent):
        """[命令: 美卡服务器] 查询 TruckersMP 美卡服务器状态。"""
        async for result in self.tmpserver(event, game_filter='ats'):
            yield result
