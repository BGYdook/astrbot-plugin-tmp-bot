"""
路况查询功能
"""

import re
from typing import List


async def tmptraffic(self, event, NetworkException, ApiResponseException):
    message_str = (event.message_str or "").strip()
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
            place_type = raw_name[idx1 + 1 : idx2].strip()
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
