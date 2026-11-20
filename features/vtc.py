"""TruckersMP VTC profiles, member roles, and history."""

import re
from typing import Optional, List, Dict, Any

from .astrbot_compat import AstrMessageEvent, logger
from .shared import (
    read_json,
    command_text,
    ApiResponseException,
    NetworkException,
    PlayerNotFoundException,
    SteamIdNotFoundException,
    _format_timestamp_to_beijing,
)


class VtcMixin:
    async def _get_vtc_detail(self, vtc_id: str) -> Dict[str, Any]:
        data = await self._get_tmp_api_json(f"vtc/{vtc_id}", 'VTC')
        response = data.get('response')
        if not isinstance(response, dict):
            raise ApiResponseException("VTC API 返回格式异常")
        return response

    async def _get_vtc_history(self, tmp_id: str) -> List[Dict[str, Any]]:
        """查询玩家的历史VTC（车队）记录。
        主接口: TruckyApp v2/truckersmp/player（含 vtc + vtcHistory）
        备用: 用户自定义源 + 内置源 evmapi.cxnnn.cn / evmapi.114512.xyz
        最后回退: TruckersMP 官方 API
        """
        if not self.session:
            return []

        def _build_item(name: str, tag: str = '', role: str = '',
                        join_date: str = '', leave_date: str = '') -> Dict[str, Any]:
            return {'vtcName': name, 'vtcTag': tag, 'role': role,
                    'joinDate': join_date, 'leaveDate': leave_date}

        # 1) TruckyApp truckersmp/player — 双层包装 {response: {error: false, response: {vtc, vtcHistory}}}
        try:
            url = f"https://api.truckyapp.com/v2/truckersmp/player?playerID={tmp_id}"
            logger.info(f"VTC历史: TruckyApp -> {url}")
            async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                if resp.status == 200:
                    data = await read_json(resp)
                    outer = data.get('response', data) if isinstance(data, dict) else {}
                    inner = outer.get('response') if isinstance(outer, dict) else None
                    if isinstance(inner, dict) and outer.get('error') is False:
                        # 检查是否开启了 VTC 历史显示
                        display_vtc_history = inner.get('displayVTCHistory')
                        if display_vtc_history is False:
                            logger.info("VTC历史: 用户设置了VTC历史为私密状态")
                            return None  # None 表示私密
                        result: List[Dict[str, Any]] = []
                        # 不包含当前车队，只返回历史车队
                        history = inner.get('vtcHistory')
                        if isinstance(history, list):
                            for h in history:
                                if isinstance(h, dict):
                                    result.append(_build_item(
                                        name=h.get('name', ''),
                                        tag=h.get('tag', ''),
                                        role=h.get('role', ''),
                                        join_date=h.get('joinDate', ''),
                                        leave_date=h.get('leftDate', ''),
                                    ))
                        if result:
                            logger.info(f"VTC历史: TruckyApp 获取到 {len(result)} 条记录")
                            return result
                        logger.info("VTC历史: TruckyApp 响应中无 VTC 数据")
                    else:
                        logger.info(f"VTC历史: TruckyApp error={outer.get('error')}")
                else:
                    logger.info(f"VTC历史: TruckyApp HTTP {resp.status}")
        except Exception as e:
            logger.error(f"VTC历史: TruckyApp 请求异常: {e}")

        # 2) 第三方 VTCM 源（用户自定义源优先，其后为内置源）
        for base in self._api_bases(self.VTC_HISTORY_API_BASES):
            try:
                url = f"{base}/vtc/history?tmpId={tmp_id}"
                logger.info(f"VTC历史: {base} -> {url}")
                async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                    if resp.status == 200:
                        data = await read_json(resp)
                        items = data.get('data') or data.get('response') or []
                        if isinstance(items, list) and items:
                            logger.info(f"VTC历史: {base} 获取到 {len(items)} 条记录")
                            return items
            except Exception as e:
                logger.error(f"VTC历史: {base} 异常: {e}")

        # 不使用官方 API 回退 - 官方 API 只返回当前 VTC，不是历史记录
        return []

    async def _get_vtc_member_role(self, tmp_id: str, vtc_info: Optional[Dict] = None) -> Optional[str]:
        """查询玩家在车队内的角色。
        优先策略：
        1) 尝试使用官方 TruckersMP VTC 角色查询 API: https://api.truckersmp.com/v2/vtc/{vtc_id}/role/{role_id}
        2) 若官方API失败，回退到第三方 VTCM 源的 vtc/memberAll/role 接口
           （源列表取自 `_api_bases()`：用户自定义源优先，内置源兜底）
        3) 若传入 vtc_info 且包含 vtcId，则直接用 vtcId 查询成员列表并匹配 tmpId
        4) 若未传入或未包含 vtcId，则尝试从 TruckersMP player 接口获取 vtc.id
        5) 若仍无 vtcId，尝试直接用 memberAll/role?tmpId=tmp_id 回退查询（部分接口支持）
        6) 若有 vtc 名称但无 vtcId，先通过 /vtc/search?name= 搜索取得 vtcId，再查询成员列表
        返回值：匹配到的角色字符串或 None
        """
        if not self.session:
            return None

        # 0) 优先尝试官方 TruckersMP VTC 角色查询 API
        # 需要先获取 vtc_id 和 role_id
        try:
            # 获取玩家信息以获取 VTC ID
            player_info = await self._get_player_info(tmp_id)
            vtc = player_info.get('vtc') if isinstance(player_info.get('vtc'), dict) else {}
            vtc_id = vtc.get('id')

            if vtc_id:
                # 获取 VTC 信息以获取角色 ID
                vtc_info_url = f"https://api.truckersmp.com/v2/vtc/{vtc_id}"
                logger.info(f"官方VTC查询: 获取VTC信息 {vtc_info_url}")
                async with self.session.get(vtc_info_url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                    if resp.status == 200:
                        vtc_data = await read_json(resp)
                        if vtc_data.get('error') is False:
                            vtc_response = vtc_data.get('response', {})
                            # 查找玩家在当前VTC中的角色
                            members = vtc_response.get('members', [])
                            for member in members:
                                if str(member.get('user_id', '')) == str(tmp_id):
                                    role_id = member.get('role_id')
                                    if role_id:
                                        # 获取角色详细信息
                                        role_url = f"https://api.truckersmp.com/v2/vtc/{vtc_id}/role/{role_id}"
                                        logger.info(f"官方VTC角色查询: {role_url}")
                                        async with self.session.get(role_url, timeout=self._cfg_int('api_timeout_seconds', 10)) as role_resp:
                                            if role_resp.status == 200:
                                                role_data = await read_json(role_resp)
                                                if role_data.get('error') is False:
                                                    role_info = role_data.get('response', {})
                                                    role_name = role_info.get('name')
                                                    if role_name:
                                                        logger.info(f"官方VTC角色查询成功: {role_name}")
                                                        return role_name
                                    break
        except Exception as e:
            logger.info(f"官方VTC角色查询异常: {e}")

        # Helper: 解析成员列表并匹配 tmp_id，返回 role 或 None
        def _find_role_in_members(members) -> Optional[str]:
            if not isinstance(members, list):
                return None
            for m in members:
                member_tmp = m.get('tmpId') or m.get('tmp_id') or m.get('tmpIdStr') or m.get('tmpid') or m.get('tmpID')
                if member_tmp and str(member_tmp) == str(tmp_id):
                    role = m.get('role') or m.get('roleName') or m.get('position') or m.get('name') or m.get('post')
                    if role:
                        return str(role)
            return None

        # 1) 尝试从传入的 vtc_info 获取 vtc_id
        vtc_id = None
        vtc_name = None
        if isinstance(vtc_info, dict):
            vtc_id = vtc_info.get('id') or vtc_info.get('vtcId') or vtc_info.get('vtc_id') or vtc_info.get('VTCId')
            vtc_name = vtc_info.get('name') or vtc_info.get('vtcName')

        # 2) 若仍无 vtc_id，尝试从 TruckersMP player 接口补充（如果调用方没有提前获取）
        if not vtc_id:
            try:
                player_info = await self._get_player_info(tmp_id)
                vtc = player_info.get('vtc') if isinstance(player_info.get('vtc'), dict) else {}
                vtc_id = vtc.get('id') or vtc.get('vtcId') or vtc.get('vtc_id') or vtc.get('VTCId')
                if not vtc_name:
                    vtc_name = vtc.get('name') or vtc.get('vtcName')
            except Exception as exc:
                logger.debug(f"补充玩家 VTC 信息失败，继续后续回退策略: {exc}")

        # 3) 如果有 vtc_id，直接用 vtcId 查询成员角色列表
        if vtc_id:
            for base in self._api_bases():
                try:
                    url_vid = f"{base}/vtc/memberAll/role?vtcId={vtc_id}"
                    logger.info(f"VTC 角色查询: 使用 vtcId 查询 {url_vid}")
                    async with self.session.get(url_vid, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                        if resp.status == 200:
                            data = await read_json(resp)
                            members = data.get('data') or data.get('response') or []
                            role = _find_role_in_members(members)
                            if role:
                                logger.info(f"VTC 角色: 通过 vtcId={vtc_id} 找到角色 {role}")
                                return role
                        else:
                            logger.info(f"VTC 角色查询(vtcId) 返回状态: {resp.status}")
                except Exception as e:
                    logger.info(f"VTC 角色查询(vtcId) 异常: {e}")

        # 4) 回退：部分接口支持用 tmpId 直接查询
        for base in self._api_bases():
            try:
                url_tmp = f"{base}/vtc/memberAll/role?tmpId={tmp_id}"
                logger.info(f"VTC 角色查询: 回退尝试 tmpId 查询 {url_tmp}")
                async with self.session.get(url_tmp, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                    if resp.status == 200:
                        data = await read_json(resp)
                        members = data.get('data') or data.get('response') or []
                        role = _find_role_in_members(members)
                        if role:
                            logger.info(f"VTC 角色: 通过 tmpId 回退查询到角色 {role}")
                            return role
                    else:
                        logger.info(f"VTC 角色查询(tmpId) 返回状态: {resp.status}")
            except Exception as e:
                logger.info(f"VTC 角色查询(tmpId) 异常: {e}")

        # 5) 若没有 vtc_id 但有 vtc_name，则先搜索 vtcId 再查询
        if not vtc_id and vtc_name:
            for base in self._api_bases():
                try:
                    from urllib.parse import quote_plus
                    qname = quote_plus(str(vtc_name))
                    search_url = f"{base}/vtc/search?name={qname}"
                    logger.info(f"VTC 车队搜索: {search_url}")
                    async with self.session.get(search_url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                        if resp.status == 200:
                            data = await read_json(resp)
                            items = data.get('data') or data.get('response') or []
                            if isinstance(items, list) and items:
                                it = items[0]
                                found_id = it.get('id') or it.get('vtcId') or it.get('vtc_id')
                                if found_id:
                                    vtc_id = found_id
                                    logger.info(f"VTC 搜索结果: name={vtc_name} -> vtcId={vtc_id}")
                                    break
                except Exception as e:
                    logger.info(f"VTC 车队搜索异常: {e}")

            # 如果通过搜索得到 vtc_id，再次用 vtcId 查询成员
            if vtc_id:
                for base in self._api_bases():
                    try:
                        url_vid2 = f"{base}/vtc/memberAll/role?vtcId={vtc_id}"
                        logger.info(f"VTC 角色查询: 通过搜索得到 vtcId 后查询 {url_vid2}")
                        async with self.session.get(url_vid2, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                            if resp.status == 200:
                                data = await read_json(resp)
                                members = data.get('data') or data.get('response') or []
                                role = _find_role_in_members(members)
                                if role:
                                    logger.info(f"VTC 角色: 通过 vtcId={vtc_id}（搜索后）找到角色 {role}")
                                    return role
                            else:
                                logger.info(f"VTC 角色查询(搜索后 vtcId) 返回状态: {resp.status}")
                    except Exception as e:
                        logger.info(f"VTC 角色查询(搜索后 vtcId) 异常: {e}")

        # 6) 最后回退：尝试用 vtcName 参数直接查询 memberAll/role（部分实现支持）
        if vtc_name:
            for base in self._api_bases():
                try:
                    from urllib.parse import quote_plus
                    qname = quote_plus(str(vtc_name))
                    url_name = f"{base}/vtc/memberAll/role?vtcName={qname}"
                    logger.info(f"VTC 最后回退: 通过 vtcName 查询 {url_name}")
                    async with self.session.get(url_name, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                        if resp.status == 200:
                            data = await read_json(resp)
                            members = data.get('data') or data.get('response') or []
                            role = _find_role_in_members(members)
                            if role:
                                logger.info(f"VTC 角色: 通过 vtcName 找到角色 {role}")
                                return role
                        else:
                            logger.info(f"VTC 角色查询(vtcName) 返回状态: {resp.status}")
                except Exception as e:
                    logger.info(f"VTC 角色查询(vtcName) 异常: {e}")

        logger.info(f"VTC 角色: 未能找到玩家 {tmp_id} 的车队角色信息")
        return None

    async def tmpvtc_info(self, event: AstrMessageEvent):
        """[命令: VTC] 按 VTC ID 查询 TruckersMP 车队资料。"""
        match = re.search(r'vtc\s*(\d+)', command_text(event), flags=re.IGNORECASE)
        if not match:
            yield event.plain_result("用法: vtc [VTC ID]")
            return
        vtc_id = match.group(1)
        try:
            detail = await self._get_vtc_detail(vtc_id)
        except NetworkException as exc:
            yield event.plain_result(f"查询 VTC 失败: {exc}")
            return
        except ApiResponseException as exc:
            yield event.plain_result(f"查询 VTC 失败: {exc}")
            return
        except Exception as exc:
            logger.error(f"查询 VTC {vtc_id} 失败: {exc}", exc_info=True)
            yield event.plain_result("查询 VTC 失败，请稍后重试")
            return

        games = detail.get('games') if isinstance(detail.get('games'), dict) else {}
        supported_games = []
        if games.get('ets'):
            supported_games.append('欧卡2')
        if games.get('ats'):
            supported_games.append('美卡')
        socials = detail.get('socials') if isinstance(detail.get('socials'), dict) else {}
        recruitment_raw = str(detail.get('recruitment') or '').strip().lower()
        recruitment = {
            'open': '开放招募',
            'closed': '停止招募',
        }.get(recruitment_raw, detail.get('recruitment') or '未知')

        message = f"车队名称: {detail.get('name') or '未命名车队'}\n"
        message += f"VTC ID: {detail.get('id') or vtc_id}\n"
        message += f"车队标签: {detail.get('tag') or '无'}\n"
        message += f"车主: {detail.get('owner_username') or '未知'}"
        if detail.get('owner_id'):
            message += f" (ID: {detail.get('owner_id')})"
        message += "\n"
        message += f"成员数量: {detail.get('members_count', 0)} 人\n"
        message += f"招募状态: {recruitment}\n"
        message += f"支持游戏: {'、'.join(supported_games) or '未知'}\n"
        message += f"主要语言: {self._translate_language(detail.get('language'))}\n"
        message += f"成立时间: {_format_timestamp_to_beijing(str(detail.get('created') or ''))}\n"
        if detail.get('slogan'):
            message += f"车队口号: {self._clean_tmp_text(detail.get('slogan'), limit=300)}\n"

        information = self._clean_tmp_text(detail.get('information'), limit=1000)
        rules = self._clean_tmp_text(detail.get('rules'), limit=800)
        requirements = self._clean_tmp_text(detail.get('requirements'), limit=800)
        if information:
            message += f"\n车队简介:\n{information}\n"
        if rules:
            message += f"\n车队规则:\n{rules}\n"
        if requirements:
            message += f"\n加入要求:\n{requirements}\n"
        if detail.get('website'):
            message += f"\n官方网站: {detail.get('website')}"
        social_links = []
        for platform in ('discord', 'twitter', 'youtube', 'twitch', 'facebook'):
            if socials.get(platform):
                social_links.append(f"{platform}: {socials.get(platform)}")
        if social_links:
            message += "\n社交链接:\n" + "\n".join(social_links)
        yield event.plain_result(message.rstrip())

    async def tmpvtc_history(self, event: AstrMessageEvent):
        """[命令: 历史车队] 查询玩家的历史VTC (车队) 记录。支持输入 TMP ID 或绑定查询。"""
        message_str = command_text(event)
        user_id = event.get_sender_id()

        target_user_id = self._mentioned_user_id(event)

        match = re.search(r'历史车队\s*(\d+)?', message_str)
        input_id = match.group(1) if match else None

        tmp_id = None
        if input_id:
            if len(input_id) == 17 and input_id.startswith('7'):
                try:
                    tmp_id = await self._get_tmp_id_from_steam_id(input_id)
                except SteamIdNotFoundException as e:
                    yield event.plain_result(str(e))
                    return
                except NetworkException as e:
                    yield event.plain_result(f"SteamID查询失败: {str(e)}\n请稍后重试或使用TMP ID查询")
                    return
            else:
                tmp_id = input_id
        else:
            bind_user_id = target_user_id or user_id
            tmp_id = self._get_bound_tmp_id(bind_user_id)

        if not tmp_id:
            yield event.plain_result("请输入正确的玩家编号 TMP ID，或者先绑定账号")
            return

        try:
            await self._get_player_info(tmp_id)
        except PlayerNotFoundException as e:
            yield event.plain_result(str(e))
            return
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
            return

        try:
            vtc_history = await self._get_vtc_history(tmp_id)
        except Exception as e:
            logger.error(f"历史车队查询异常: {e}")
            yield event.plain_result("查询历史车队失败，请稍后重试")
            return

        if vtc_history is None:
            yield event.plain_result("该用户的历史车队为私密状态")
            return
        if not vtc_history:
            yield event.plain_result("暂无历史车队记录")
            return

        lines = []
        for idx, vtc_item in enumerate(vtc_history[:10], 1):
            vtc_name = vtc_item.get('vtcName') or vtc_item.get('name') or vtc_item.get('vtc_name') or '未知'
            vtc_tag = vtc_item.get('vtcTag') or vtc_item.get('tag') or vtc_item.get('vtc_tag', '')
            join_date = vtc_item.get('joinDate') or vtc_item.get('join_date') or vtc_item.get('joinedAt', '')
            leave_date = vtc_item.get('leaveDate') or vtc_item.get('leave_date') or vtc_item.get('leftAt', '')
            role = vtc_item.get('role') or vtc_item.get('position') or vtc_item.get('vtcRole', '')

            entry = f"{idx}. {vtc_name}"
            if vtc_tag:
                entry += f" [{vtc_tag}]"
            if role:
                entry += f"\n   职位: {role}"
            if join_date:
                entry += f"\n   加入时间: {join_date}"
            if leave_date:
                entry += f"\n   离开时间: {leave_date}"
            lines.append(entry)

        message = "\n".join(lines)
        if len(vtc_history) > 10:
            message += f"\n\n... 共 {len(vtc_history)} 条记录，仅显示前10条"

        yield event.plain_result(message)
