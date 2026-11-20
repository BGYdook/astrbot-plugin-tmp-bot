"""Map tiles, coordinates, and the shared player map cache."""

import asyncio
import base64
import math
import re
import time
from typing import Optional, List, Dict, Tuple, Any
from urllib.parse import urlsplit

import aiohttp

from .astrbot_compat import logger
from .shared import read_json
from .shared import NetworkException, is_safe_http_url


class MapMixin:
    def _tile_url(self, layer: str, default: str) -> str:
        """地图瓦片地址：用户自定义的优先，否则用传入的默认值。

        自定义地址必须带 `{z}` / `{x}` / `{y}` 占位符，否则忽略并回退默认值。
        """
        raw = self._cfg_str(f'extra_tile_{layer}_url', '').strip()
        if not raw:
            return default
        if not raw.lower().startswith(("http://", "https://")):
            raw = "https://" + raw
        missing = [k for k in ("{z}", "{x}", "{y}") if k not in raw]
        if missing:
            logger.warning(f"忽略无效的 {layer} 瓦片地址（缺少 {'/'.join(missing)} 占位符）: {raw}")
            return default
        try:
            parsed = urlsplit(raw)
            if not is_safe_http_url(raw, allow_local_http=True) or not parsed.hostname or parsed.port == 0:
                raise ValueError('无效的瓦片地址')
        except ValueError:
            logger.warning(f"忽略格式无效的 {layer} 瓦片地址")
            return default
        return raw

    async def _prepare_location_basemap(self, layer: str, x: float, y: float) -> Dict[str, Any]:
        """Embed visible tracker tiles so the remote renderer need not fetch them."""
        if not self.session:
            raise NetworkException("地图 HTTP 会话不可用")

        async def read_limited(response: Any, limit: int) -> bytes:
            chunks = []
            size = 0
            async for chunk in response.content.iter_chunked(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('地图响应超过大小限制')
                chunks.append(chunk)
            return b''.join(chunks)

        sources = getattr(self, '_location_tracker_sources', None)
        if not sources or time.monotonic() >= getattr(self, '_location_tracker_sources_until', 0):
            sources = {
                'ets': ('https://map-cdn.krashnz.com/ets2map/ets2/v1.62', -22, -22, -100, 88, -124, 91),
                'promods': ('https://map-cdn.krashnz.com/ets2map/promods/v2.80', -145, -18, -144, 206, -166, 130),
            }
            try:
                async with self.session.get('https://ets2map.com/assets/app.js', timeout=aiohttp.ClientTimeout(total=5)) as response:
                    response.raise_for_status()
                    script = await read_limited(response, 2 * 1024 * 1024)
                text = script.decode('utf-8')
                for key, game in (('ets', 'ETS2'), ('promods', 'PROMODS')):
                    match = re.search(
                        rf'{game}:\{{defaultCamera:\{{[^}}]+\}},tileUrl:"([^"]+)",'
                        r'tileOffset:\{x:([\d.-]+),y:([\d.-]+)\},'
                        r'tileRange:\{xMin:([\d-]+),xMax:([\d-]+),yMin:([\d-]+),yMax:([\d-]+)\}',
                        text,
                    )
                    if match and re.fullmatch(r'https://map-cdn\.krashnz\.com/ets2map/(?:ets2|promods)/v[\w.-]+', match[1]):
                        sources[key] = (match[1], *(float(match[i]) for i in range(2, 8)))
                cache_seconds = 3600
            except Exception as exc:
                logger.warning(f"定位: 获取追踪地图配置失败，使用内置地图配置 ({type(exc).__name__})")
                cache_seconds = 60
            self._location_tracker_sources = sources
            self._location_tracker_sources_until = time.monotonic() + cache_seconds

        base, offset_x, offset_y, xmin, xmax, ymin, ymax = sources[layer]
        center_x, center_y = self._tracker_map_coordinates(x, y, layer)
        pixel_scale = 0.2499
        half_width, half_height = 640 / (pixel_scale * 2), 360 / (pixel_scale * 2)
        left = max(int(xmin), math.floor((center_x - half_width - offset_x + 500) / 1000))
        right = min(int(xmax), math.floor((center_x + half_width - offset_x + 500) / 1000))
        top = max(int(ymin), math.floor((center_y - half_height - offset_y + 500) / 1000))
        bottom = min(int(ymax), math.floor((center_y + half_height - offset_y + 500) / 1000))
        semaphore = asyncio.Semaphore(6)

        async def fetch_tile(tx: int, ty: int) -> Dict[str, Any]:
            async with semaphore:
                url = f'{base}/{tx}_{ty}.png'
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as response:
                    response.raise_for_status()
                    content = await read_limited(response, 1024 * 1024)
                if not content.startswith(b'\x89PNG\r\n\x1a\n') or not content.endswith(b'IEND\xaeB`\x82'):
                    raise ValueError('地图瓦片不是有效的 PNG 图片')
                return {
                    'url': 'data:image/png;base64,' + base64.b64encode(content).decode('ascii'),
                    'left': tx * 1000 + offset_x - 500,
                    'top': ty * 1000 + offset_y - 500,
                }

        results = await asyncio.gather(
            *(fetch_tile(tx, ty) for tx in range(left, right + 1) for ty in range(top, bottom + 1)),
            return_exceptions=True,
        )
        images = [result for result in results if isinstance(result, dict)]
        if not images or len(images) != len(results):
            raise NetworkException(f"定位地图瓦片加载不完整 ({len(images)}/{len(results)})，请稍后重试")
        logger.info(f"定位: 底图瓦片已加载 source={base} tiles={len(images)} center=({x},{y})")
        return {
            'images': images, 'trackerTiles': True, 'ukCorrection': layer == 'ets',
            'pixelScale': pixel_scale, 'maxZoom': 0, 'minZoom': 0, 'viewZoom': 1,
            'world': [xmin * 1000 + offset_x - 500, ymin * 1000 + offset_y - 500,
                      xmax * 1000 + offset_x + 500, ymax * 1000 + offset_y + 500],
        }

    @staticmethod
    def _location_map_profile(layer: str, tile_url: str) -> Dict[str, Any]:
        """Keep tile size and game-coordinate projection paired with the source."""
        host = (urlsplit(tile_url).hostname or '').lower()
        if host == 'ets2.online':
            extent = (
                [-135110.156, 168923.75, -179273.531, 124760.375]
                if layer == 'promods'
                else [-113177.313, 97925.625, -122648.086, 88454.85]
            )
            return {
                'tileUrl': tile_url, 'tileSize': 256,
                'bounds': {'x': 65536, 'y': 65536},
                'maxZoom': 8, 'minZoom': 2,
                'extent': extent,
            }
        # Retain the projection expected by existing custom 512px tile sources.
        profile = {
            'tileUrl': tile_url, 'tileSize': 512,
            'bounds': {'x': 131072, 'y': 131072},
            'maxZoom': 8, 'minZoom': 2,
        }
        if layer == 'ets':
            profile['extent'] = [-113177.305, 97925.63, -122648.086, 88454.85]
        else:
            profile.update({'scale': 2.598541, 'origin': [51953, 76024]})
        return profile

    @staticmethod
    def _tracker_map_coordinates(x: float, y: float, layer: str) -> Tuple[float, float]:
        # ETS2Map scales the original UK region separately; tiles are already scaled.
        if layer == 'ets' and x < -30100 and -86000 < y < -0.14 * x - 10040:
            return 0.75 * x - 8337, 0.75 * y - 1000
        return x, y

    def _get_fullmap_interval(self) -> int:
        v = self._cfg_int('ets2map_fullmap_interval_seconds', 60)
        return 60 if v < 60 else v

    async def _fetch_fullmap(self) -> None:
        # Concurrent location lookups wait for the same refresh before reading the cache.
        async with self._fullmap_fetch_lock:
            session = self.session
            if session is None:
                return
            now = time.monotonic()
            if now < self._fullmap_next_fetch_ts:
                return
            self._fullmap_next_fetch_ts = now + self._get_fullmap_interval()

            url = "https://tracker.ets2map.com/v3/fullmap"
            timeout = max(1, self._cfg_int('api_timeout_seconds', 10))
            try:
                async with session.get(url, timeout=timeout) as response:
                    if response.status != 200:
                        logger.info(f"fullmap 拉取失败 status={response.status}")
                        return
                    data = await read_json(response)
                    if self._fullmap_players(data) is None:
                        logger.warning("fullmap 响应缺少玩家列表")
                        return
                    self._fullmap_cache = data
                    self._fullmap_cache_ts = time.monotonic()
                    logger.info("fullmap 拉取成功")
            except asyncio.CancelledError:
                self._fullmap_next_fetch_ts = 0.0
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
                logger.warning(f"fullmap 拉取失败: {exc}")

    def _get_fullmap_tile_url(self, map_type: str) -> Optional[str]:
        data = self._fullmap_cache or {}
        candidates: List[str] = []
        def walk(v: Any) -> None:
            if isinstance(v, dict):
                for val in v.values():
                    walk(val)
                return
            if isinstance(v, list):
                for val in v:
                    walk(val)
                return
            if isinstance(v, str):
                s = v.strip()
                if s.startswith(("http://", "https://")) and "{z}" in s and "{x}" in s and "{y}" in s:
                    try:
                        hostname = (urlsplit(s).hostname or "").lower()
                    except ValueError:
                        return
                    if is_safe_http_url(s) and hostname in {
                        "map-cdn.krashnz.com", "ets2.online",
                        "ets-map.oss-cn-beijing.aliyuncs.com", "ets_tiles.cnly.top",
                    }:
                        candidates.append(s)
        if isinstance(data, dict):
            if data.get('Data'):
                walk(data.get('Data'))
            if data.get('data'):
                walk(data.get('data'))
            walk(data)
        else:
            walk(data)
        if not candidates:
            return None
        seen = set()
        uniq = []
        for c in candidates:
            if c in seen:
                continue
            seen.add(c)
            uniq.append(c)
        candidates = uniq
        if map_type == "promods":
            for c in candidates:
                if "promods" in c.lower():
                    return c
        for c in candidates:
            lc = c.lower()
            if "ets" in lc and "promods" not in lc:
                return c
        return candidates[0]

    @staticmethod
    def _fullmap_players(data: Any) -> Optional[List[Any]]:
        if isinstance(data, dict):
            for key in ('Data', 'data', 'players'):
                players = data.get(key)
                if isinstance(players, list):
                    return players
        return None

    def _fresh_fullmap_players(self) -> List[Any]:
        # A failed refresh can reuse a recent snapshot, but cannot imply online status indefinitely.
        age = time.monotonic() - self._fullmap_cache_ts
        ttl = min(2 * self._get_fullmap_interval(), 300)
        if not (0 <= age < ttl):
            return []
        return self._fullmap_players(self._fullmap_cache) or []

    def _get_fullmap_player(self, tmp_id: str) -> Optional[Dict[str, Any]]:
        payload = self._fresh_fullmap_players()
        tid = str(tmp_id)
        for p in payload:
            if not isinstance(p, dict):
                continue
            mp_id = p.get('MpId') or p.get('mp_id') or p.get('tmpId') or p.get('tmp_id')
            if mp_id is None:
                continue
            if str(mp_id) == tid:
                return p
        return None

    @staticmethod
    def _finite_number(value: Any) -> Optional[float]:
        if isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return number if math.isfinite(number) else None

    @classmethod
    def _read_map_coordinates(cls, item: Any) -> Optional[Tuple[float, float]]:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            x, y = cls._finite_number(item[0]), cls._finite_number(item[1])
        elif isinstance(item, dict):
            def read_axis(*keys: str) -> Optional[float]:
                for key in keys:
                    number = cls._finite_number(item.get(key))
                    if number is not None:
                        return number
                return None

            x = read_axis('axisX', 'x', 'X', 'posX', 'pos_x')
            y = read_axis('axisY', 'y', 'Y', 'posY', 'pos_y')
        else:
            return None
        return (x, y) if x is not None and y is not None else None
