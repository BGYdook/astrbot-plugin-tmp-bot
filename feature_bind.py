"""
绑定与解绑功能
"""

import re


async def tmpbind(self, event, PlayerNotFoundException, SteamIdNotFoundException):
    message_str = event.message_str.strip()
    user_id = event.get_sender_id()

    match = re.search(r"绑定\s*(\d+)", message_str)
    input_id = match.group(1) if match else None

    if not input_id:
        yield event.plain_result("请输入正确的玩家编号，格式：绑定 [TMP ID] 或 绑定 [Steam ID]")
        return

    tmp_id = input_id
    is_steam_id = len(input_id) == 17 and input_id.startswith("7")

    if is_steam_id:
        try:
            tmp_id = await self._get_tmp_id_from_steam_id(input_id)
        except SteamIdNotFoundException:
            yield event.plain_result(f"Steam ID {input_id} 未在 TruckersMP 中注册，无法绑定。")
            return
        except Exception:
            yield event.plain_result("Steam ID 转换服务请求失败，请稍后再试。")
            return

    try:
        player_info = await self._get_player_info(tmp_id)
    except PlayerNotFoundException:
        yield event.plain_result("玩家不存在，请检查ID是否正确")
        return
    except Exception as e:
        yield event.plain_result(f"查询失败: {str(e)}")
        return

    player_name = player_info.get("name", "未知玩家")

    if self._bind_tmp_id(user_id, tmp_id, player_name):
        yield event.plain_result(f"绑定成功！\n已绑定TMP玩家 {player_name} (ID: {tmp_id})")
    else:
        yield event.plain_result("绑定失败，请稍后重试")


async def tmpunbind(self, event):
    user_id = event.get_sender_id()
    user_binding = self._load_bindings().get(user_id, {})
    tmp_id = user_binding.get("tmp_id")

    if not tmp_id:
        yield event.plain_result("您还没有绑定任何TMP账号")
        return

    player_name = user_binding.get("player_name", "未知玩家")

    if self._unbind_tmp_id(user_id):
        yield event.plain_result(f"解绑成功！\n已解除与TMP玩家 {player_name}的绑定")
    else:
        yield event.plain_result("解绑失败，请稍后重试")
