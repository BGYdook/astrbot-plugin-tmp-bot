"""TruckersMP player bans and violation output."""

import asyncio
import re
from typing import Optional, List, Dict, Tuple

import aiohttp

from .astrbot_compat import AstrMessageEvent, logger
from .shared import (
    read_json,
    ApiResponseException,
    NetworkException,
    PlayerNotFoundException,
    _format_timestamp_to_beijing,
    _is_hidden_ban_expiry,
    _is_hidden_ban_reason,
    _is_permanent_ban_expiry,
)


class ViolationsMixin:
    async def _get_player_bans(self, tmp_id: str) -> List[Dict]:
        if not self.session:
            raise NetworkException("插件初始化中，HTTP会话不可用")

        try:
            url = f"https://api.truckersmp.com/v2/bans/{tmp_id}"
            async with self.session.get(url, timeout=10) as response:
                if response.status != 200:
                    raise ApiResponseException(f"封禁 API 返回错误状态码: {response.status}")
                data = await read_json(response)
                if not isinstance(data, dict):
                    raise ApiResponseException("封禁 API 返回格式异常")
                if data.get('error'):
                    detail = data.get('descriptor') or data.get('message') or "未知 API 错误"
                    raise ApiResponseException(f"封禁 API 查询失败: {detail}")

                bans = data.get('response') if 'response' in data else data.get('data')
                if not isinstance(bans, list):
                    raise ApiResponseException("封禁 API 未返回有效的违规记录列表")
                logger.info(f"Bans API 提取后: keys={list(data.keys())}, count={len(bans)}")
                return bans
        except (ApiResponseException, NetworkException):
            raise
        except asyncio.TimeoutError as e:
            logger.error(f"获取玩家封禁超时: {e}", exc_info=False)
            raise NetworkException("封禁 API 请求超时") from e
        except aiohttp.ClientError as e:
            logger.error(f"获取玩家封禁网络失败: {e}", exc_info=False)
            raise NetworkException("封禁 API 网络请求失败") from e
        except Exception as e:
            logger.error(f"获取玩家封禁失败: {e}", exc_info=False)
            raise NetworkException(f"封禁记录查询失败: {e}") from e

    def _format_ban_info(self, bans_info: List[Dict]) -> Tuple[int, List[Dict]]:
        """只返回历史封禁次数和最新的封禁记录（按时间倒序）"""
        if not bans_info or not isinstance(bans_info, list):
            return 0, []

        valid_bans = [ban for ban in bans_info if isinstance(ban, dict)]
        sorted_bans = sorted(valid_bans, key=lambda x: str(x.get('timeAdded') or ''), reverse=True)
        return len(valid_bans), sorted_bans

    def _translate_ban_reason(self, reason: Optional[str]) -> str:
        """将封禁原因中的所有片段（§X.X - 英文）翻译为中文，保留后续说明/链接。

        支持多段原因，例如：
        输入："§2.2 - Collisions, §2.5 - Reckless Driving - https://youtu.be/xxx // 30 days due to history (§2.8)"
        输出："§2.2 - 碰撞, §2.5 - 鲁莽驾驶 - https://youtu.be/xxx // 因历史违规追加30天 (§2.8 历史原因)"
        """
        if not reason or not isinstance(reason, str):
            return reason or ""

        zh_map = {
            "1.1": "账号、设备与游戏设置责任",
            "1.2": "逃避封禁",
            "1.3": "个人信息与隐私",
            "1.4": "不当内容与交流",
            "1.5": "语言、头像和昵称违规",
            "1.6": "冒充官方或其他玩家",
            "1.7": "刷屏/滥用系统",
            "2.1": "黑客/漏洞/功能滥用",
            "2.2": "碰撞",
            "2.3": "堵塞",
            "2.4": "错误驾驶方式/不当超车",
            "2.5": "鲁莽驾驶",
            "2.6": "骚扰、侮辱或不当行为",
            "2.7": "特色区域和事件服务器规则",
            "2.8": "历史原因",
            "2.9": "保存修改",
            "3": "保存编辑",
            "3.1": "违规保存编辑",
            "3.2": "不兼容或缺失组件",        }
        keyword_map = {
            "collisions": "碰撞",
            "reckless driving": "鲁莽驾驶",
            "blocking": "堵塞",
            "trolling": "恶意捣乱",
            "inappropriate overtaking": "不当超车",
            "wrong way": "逆行",
            "ramming": "蓄意撞车",
            "chat abuse": "聊天滥用",
            "insulting": "辱骂他人",
        }

        matches = list(re.finditer(r"§\s*(?P<code>\d+\.\d+)\s*-\s*(?P<title>[^,\-]+)", reason))
        if matches:
            parts = []
            for m in matches:
                code = m.group("code").strip()
                title = m.group("title").strip()
                zh_title = zh_map.get(code)
                if zh_title:
                    parts.append(f"§{code} - {zh_title}")
                else:
                    parts.append(f"§{code} - {title}")
            remainder = reason[matches[-1].end():]
            result = ", ".join(parts) + remainder
        else:
            result = reason

        for en, zh in keyword_map.items():
            pattern = r"\b" + re.escape(en) + r"\b"
            result = re.sub(pattern, zh, result, flags=re.IGNORECASE)

        duration_units = {
            'day': '天',
            'week': '周',
            'month': '个月',
            'year': '年',
        }

        def _translate_history_duration(match: re.Match) -> str:
            amount = match.group('amount')
            unit = match.group('unit').lower().rstrip('s')
            return f"因历史违规追加{amount}{duration_units[unit]}"

        result = re.sub(
            r"\b(?P<amount>\d+)\s+(?P<unit>days?|weeks?|months?|years?)\s+due\s+to\s+history\b",
            _translate_history_duration,
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"\bdue\s+to\s+history\b", "因历史违规", result, flags=re.IGNORECASE)
        result = re.sub(r"§\s*2\.8(?!\s*-)", "§2.8 历史原因", result, flags=re.IGNORECASE)

        return result

    async def tmpviolations(self, event: AstrMessageEvent):
        """[命令: 查违规] 查询玩家公开的 TMP 违规记录。"""
        tmp_id, id_error = await self._resolve_tmp_id_for_user_command(event, "查违规")
        if id_error:
            yield event.plain_result(id_error)
            return

        try:
            player_info, bans = await asyncio.gather(
                self._get_player_info(tmp_id),
                self._get_player_bans(tmp_id),
            )
        except PlayerNotFoundException as exc:
            yield event.plain_result(str(exc))
            return
        except NetworkException as exc:
            yield event.plain_result(f"查询违规记录失败: {exc}")
            return
        except ApiResponseException as exc:
            yield event.plain_result(f"查询违规记录失败: {exc}")
            return
        except Exception as exc:
            logger.error(f"查询玩家 {tmp_id} 违规记录失败: {exc}", exc_info=True)
            yield event.plain_result("查询违规记录失败，请稍后重试")
            return

        player_name = player_info.get('name') or '未知玩家'
        is_banned = bool(player_info.get('banned'))
        ban_count, sorted_bans = self._format_ban_info(bans)
        try:
            ban_count = int(str(player_info.get('bansCount')))
        except (TypeError, ValueError):
            pass

        message = "🚫 TMP 违规记录\n"
        message += "=" * 18 + "\n"
        message += f"玩家: {player_name} (ID: {tmp_id})\n"
        message += f"当前状态: {'封禁中' if is_banned else '正常'}\n"
        message += f"历史封禁: {ban_count} 次\n"

        if is_banned:
            banned_until = player_info.get('bannedUntil')
            active_ban = next((
                ban for ban in sorted_bans
                if ban.get('active') is True
                or str(ban.get('active')).strip().lower() in {'1', 'true', 'yes'}
            ), None)
            if not banned_until and active_ban:
                banned_until = active_ban.get('expiration')
            if _is_permanent_ban_expiry(banned_until):
                expiry = "永久"
                message += f"当前封禁截止: {expiry}\n"
            elif _is_hidden_ban_expiry(banned_until):
                message += "当前封禁截止: 该用户的封禁截止被隐藏\n"
            else:
                expiry = _format_timestamp_to_beijing(str(banned_until))
                message += f"当前封禁截止: {expiry}\n"

        if not sorted_bans:
            if is_banned or ban_count > 0:
                message += "\n该用户的封禁原因被隐藏。"
            else:
                message += "\n未查询到公开的违规记录。\n"
                message += "注：如果玩家隐藏了封禁记录，这里也不会显示。"
            yield event.plain_result(message)
            return

        message += f"\n违规记录（共 {len(sorted_bans)} 条）"
        for index, ban in enumerate(sorted_bans, 1):
            active_raw = ban.get('active')
            active = active_raw is True or str(active_raw).strip().lower() in {'1', 'true', 'yes'}
            added = _format_timestamp_to_beijing(str(ban.get('timeAdded') or ''))
            reason_raw = str(ban.get('reason') or '').strip()
            reason = (
                "该用户的封禁原因被隐藏"
                if not reason_raw or _is_hidden_ban_reason(reason_raw)
                else self._translate_ban_reason(reason_raw) or reason_raw
            )
            expiration_raw = str(ban.get('expiration') or '').strip()
            if active and not expiration_raw:
                expiration_raw = str(player_info.get('bannedUntil') or '').strip()
            if _is_permanent_ban_expiry(expiration_raw):
                expiration = "永久"
            elif _is_hidden_ban_expiry(expiration_raw):
                expiration = "该用户的封禁截止被隐藏"
            else:
                expiration = _format_timestamp_to_beijing(expiration_raw)
            admin_name = str(ban.get('adminName') or '').strip()
            admin_id = ban.get('adminID')

            message += f"\n\n{index}. {'🔴 生效中' if active else '⚪ 已结束'}"
            message += f"\n记录时间: {added}"
            message += f"\n违规原因: {reason}"
            message += f"\n封禁截止: {expiration}"
            if admin_name or admin_id:
                admin_display = admin_name or '未知GM'
                if admin_id is not None:
                    admin_display += f" (ID: {admin_id})"
                message += f"\n处理GM: {admin_display}"

        yield event.plain_result(message)
