"""TMP account binding commands and persistence."""

import time
import json
import os
import re
import tempfile
from typing import Optional, Dict, Any

from .astrbot_compat import AstrMessageEvent, logger
from .shared import NetworkException, PlayerNotFoundException, SteamIdNotFoundException, command_text


class BindingMixin:
    def _load_bindings(self, *, strict: bool = False) -> Dict[str, Any]:
        try:
            if os.path.getsize(self.bind_file) > 2 * 1024 * 1024:
                raise ValueError('绑定数据文件超过大小限制')
            with open(self.bind_file, 'r', encoding='utf-8') as f:
                bindings = json.load(f)
            if not isinstance(bindings, dict):
                raise ValueError('绑定数据必须是 JSON 对象')
            return bindings
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            logger.error(f"加载绑定数据失败: {e}")
            if strict:
                raise
            return {}

    def _save_bindings(self, bindings: dict) -> bool:
        temp_path = None
        try:
            directory = os.path.dirname(os.path.abspath(self.bind_file))
            with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', dir=directory, prefix='.bindings-', delete=False,
            ) as f:
                temp_path = f.name
                json.dump(bindings, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.bind_file)
            temp_path = None
            return True
        except (OSError, TypeError, ValueError) as e:
            logger.error(f"保存绑定数据失败: {e}")
            return False
        finally:
            if temp_path is not None:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass
                except OSError as e:
                    logger.warning(f"清理绑定临时文件失败: {e}")

    def _get_bound_tmp_id(self, user_id: str) -> Optional[str]:
        bindings = self._load_bindings()
        user_binding = bindings.get(user_id)
        if isinstance(user_binding, dict):
            return user_binding.get('tmp_id')
        return user_binding

    def _bind_tmp_id(self, user_id: str, tmp_id: str, player_name: str) -> bool:
        try:
            bindings = self._load_bindings(strict=True)
        except (OSError, ValueError):
            return False
        bindings[user_id] = {
            'tmp_id': tmp_id,
            'player_name': player_name,
            'bind_time': time.time()
        }
        return self._save_bindings(bindings)

    def _unbind_tmp_id(self, user_id: str) -> bool:
        try:
            bindings = self._load_bindings(strict=True)
        except (OSError, ValueError):
            return False
        if user_id in bindings:
            del bindings[user_id]
            return self._save_bindings(bindings)
        return False

    async def tmpbind(self, event: AstrMessageEvent):
        """[命令: 绑定] 绑定您的聊天账号与TMP ID。支持输入 TMP ID 或 Steam ID。"""
        user_id = str(event.get_sender_id() or '').strip()
        if not user_id:
            yield event.plain_result("未获取到你的账号 ID，无法绑定")
            return

        match = re.fullmatch(r'绑定\s*([0-9]+)', command_text(event))
        input_id = match.group(1) if match else None

        if not input_id:
            yield event.plain_result("请输入正确的玩家编号，格式：绑定 [TMP ID] 或 绑定 [Steam ID]")
            return

        tmp_id = input_id
        is_steam_id = (len(input_id) == 17 and input_id.startswith('7'))

        if is_steam_id:
            try:
                # 使用 TruckersMP 官方 API 直接查询
                tmp_id = await self._get_tmp_id_from_steam_id(input_id)
            except SteamIdNotFoundException as e:
                # SteamID 未注册
                yield event.plain_result(str(e))
                return
            except NetworkException as e:
                # 网络错误，建议重试
                yield event.plain_result(f"SteamID绑定失败: {str(e)}\n请稍后重试或使用TMP ID绑定")
                return
            except Exception:
                yield event.plain_result("Steam ID 查询服务请求失败，请直接使用TMP ID绑定。\n\n格式：绑定 [TMP ID]")
                return

        try:
            player_info = await self._get_player_info(tmp_id)
        except PlayerNotFoundException:
            yield event.plain_result("玩家不存在，请检查ID是否正确")
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return

        player_name = player_info.get('name', '未知')

        if self._bind_tmp_id(user_id, tmp_id, player_name):

            message = "绑定成功！\n"
            message += f"已将您的账号与TMP玩家 {player_name} (ID: {tmp_id}) 绑定"
            yield event.plain_result(message)
        else:
            yield event.plain_result("绑定失败，请稍后重试")

    async def tmpunbind(self, event: AstrMessageEvent):
        """[命令: 解绑] 解除当前用户的TruckersMP ID绑定。"""
        user_id = str(event.get_sender_id() or '').strip()
        if not user_id:
            yield event.plain_result("未获取到你的账号 ID，无法解绑")
            return
        try:
            user_binding = self._load_bindings(strict=True).get(user_id)
        except (OSError, ValueError):
            yield event.plain_result("暂时无法读取绑定数据，解绑未执行")
            return
        tmp_id = user_binding.get('tmp_id') if isinstance(user_binding, dict) else user_binding

        if not tmp_id:
            yield event.plain_result("您还没有绑定任何TMP账号")
            return

        player_name = '未知玩家'
        if isinstance(user_binding, dict):
            player_name = user_binding.get('player_name') or player_name

        if self._unbind_tmp_id(user_id):
            yield event.plain_result(f"解绑成功！\n已解除与TMP玩家 {player_name}的绑定")
        else:
            yield event.plain_result("解绑失败，请稍后重试")
