"""TruckersMP traffic conditions."""

import asyncio
import re
from typing import Dict, List

import aiohttp

from .astrbot_compat import AstrMessageEvent, logger
from .shared import read_json
from .shared import command_text, ApiResponseException, NetworkException


class TrafficMixin:
    async def _get_traffic_top(self, server_key: str) -> List[Dict]:
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")
        key = (server_key or "").strip().lower()
        alias = {
            "s1": "sim1",
            "s2": "sim2",
            "p": "eupromods1",
            "a": "arc1",
        }
        server = alias.get(key, key)
        if not server:
            raise ApiResponseException("无效的服务器标识")
        url = f"https://api.truckyapp.com/v2/traffic/top?game=ets2&server={server}"
        logger.info(f"路况: 请求 URL={url}")
        try:
            async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                status = resp.status
                if status == 200:
                    data = await read_json(resp)
                    items = data.get('response') if isinstance(data, dict) else data
                    if isinstance(items, list):
                        return items
                    raise ApiResponseException("路况 API 数据结构异常")
                if status == 404:
                    return []
                raise ApiResponseException(f"路况 API 返回错误状态码: {status}")
        except aiohttp.ClientError as e:
            logger.error(f"路况 API 网络请求失败 (aiohttp.ClientError): {e}")
            raise NetworkException("路况 API 网络请求失败")
        except asyncio.TimeoutError:
            logger.error("请求 路况 API 超时")
            raise NetworkException("请求 路况 API 超时")
        except Exception as e:
            logger.error(f"查询路况时发生未知错误: {e}", exc_info=True)
            raise NetworkException("查询路况失败")

    async def _resolve_server_ids(self, server_key: str) -> List[str]:
        if not self.session:
            return []
        key = str(server_key or "").strip().lower()
        if not key:
            return []
        if key.isdigit():
            return [key]
        patterns = []
        if key in ["sim1", "simulation1", "simulation_1"]:
            patterns = ["simulation 1", "sim 1", "sim1"]
        elif key in ["sim2", "simulation2", "simulation_2"]:
            patterns = ["simulation 2", "sim 2", "sim2"]
        elif key in ["arc1", "arc", "arcade"]:
            patterns = ["arcade", "arc 1", "arc1"]
        elif key in ["eupromods1", "promods", "promods1"]:
            patterns = ["promods", "pro mods"]
        else:
            patterns = [key]
        url = "https://api.truckersmp.com/v2/servers"
        try:
            async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                if resp.status != 200:
                    return []
                data = await read_json(resp)
        except Exception:
            return []
        servers = data.get('response') if isinstance(data, dict) else None
        if not isinstance(servers, list):
            return []
        ids = []
        for s in servers:
            if not isinstance(s, dict):
                continue
            name = str(s.get('name') or "").lower()
            sid = s.get('id') or s.get('serverId') or s.get('server_id')
            if not sid:
                continue
            for p in patterns:
                if p and p in name:
                    ids.append(str(sid))
                    break
        seen = set()
        uniq = []
        for sid in ids:
            if sid in seen:
                continue
            seen.add(sid)
            uniq.append(sid)
        return uniq

    async def tmptraffic(self, event: AstrMessageEvent):
        message_str = (command_text(event)).strip()
        m = re.search(r"路况\s*(\S+)", message_str)
        server_token = m.group(1).strip().lower() if m else ""
        if not server_token:
            yield event.plain_result("用法: 路况 [服务器简称]，例如: 路况 s1")
            return
        try:
            items = await self._get_traffic_top(server_token)
        except NetworkException as e:
            yield event.plain_result(f"查询路况失败: {str(e)}")
            return
        except ApiResponseException:
            yield event.plain_result("查询路况失败: API 返回数据异常。")
            return
        except Exception:
            yield event.plain_result("查询路况时发生未知错误。")
            return
        if not items:
            yield event.plain_result("当前服务器暂无热门路段数据。")
            return
        severity_map = {
            "Fluid": "🟢畅通",
            "Moderate": "🟠正常",
            "Congested": "🔴缓慢",
            "Heavy": "🟣拥堵",
        }
        type_map = {
            "City": "城市",
            "Road": "公路",
            "Intersection": "十字路口",
        }
        lines: List[str] = []
        for t in items:
            country_raw = str(t.get("country") or "").strip()
            country_cn, _ = await self._translate_country_city(country_raw, None)
            country = country_cn or "未知区域"
            raw_name = str(t.get("name") or "").strip()
            name = raw_name
            place_type = ""
            idx1 = raw_name.rfind("(")
            idx2 = raw_name.rfind(")")
            if idx1 > 0 and idx2 > idx1:
                name = raw_name[:idx1].strip()
                place_type = raw_name[idx1 + 1:idx2].strip()
            translated_name = await self._translate_traffic_name(name)
            severity_key = str(t.get("newSeverity") or "").strip()
            severity_text = severity_map.get(severity_key) or severity_key or "未知"
            if severity_text and severity_text == severity_key:
                translated_severity = await self._translate_text(severity_text, cache=True)
                if translated_severity:
                    severity_text = translated_severity
            players = t.get("players")
            players_str = ""
            if isinstance(players, (int, float)):
                players_str = str(int(players))
            elif players is not None:
                players_str = str(players)
            line = f"{country} {translated_name}"
            if place_type:
                type_text = type_map.get(place_type, place_type)
                if type_text and type_text == place_type:
                    translated_type = await self._translate_text(type_text, cache=True)
                    if translated_type:
                        type_text = translated_type
                line += f" ({type_text})"
            line += f"\n路况: {severity_text}"
            if players_str:
                line += f" | 人数: {players_str}"
            lines.append(line)
        header = "🚦 服务器热门路况\n" + "=" * 20
        message = header + "\n" + "\n\n".join(lines)
        yield event.plain_result(message)
