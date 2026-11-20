"""Map DLC lookup and image output."""

import asyncio
import base64
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import aiohttp

from .astrbot_compat import AstrMessageEvent, Image, logger
from .shared import read_json
from .shared import ApiResponseException, NetworkException


class DlcMixin:
    DLC_IMAGE_HOSTS = frozenset({
        'cdn.steamstatic.com', 'cdn.cloudflare.steamstatic.com', 'cdn.akamai.steamstatic.com',
        'cdn.fastly.steamstatic.com', 'shared.cloudflare.steamstatic.com',
        'shared.akamai.steamstatic.com', 'shared.fastly.steamstatic.com',
        'store.cloudflare.steamstatic.com', 'store.akamai.steamstatic.com',
        'store.fastly.steamstatic.com', 'steamcdn-a.akamaihd.net',
        'shared.steamstatic.com',
    })

    @classmethod
    def _is_dlc_header_url(cls, url: str) -> bool:
        try:
            parsed = urlsplit(url)
            if (
                parsed.scheme != 'https' or parsed.hostname not in cls.DLC_IMAGE_HOSTS
                or parsed.username is not None or parsed.port not in (None, 443)
                or parsed.fragment
            ):
                return False
        except ValueError:
            return False
        return bool(re.fullmatch(
            r'/(?:store_item_assets/)?steam/apps/[0-9]+/(?:[a-z0-9_-]+/)*[a-z0-9_.-]+\.(?:jpe?g|png|webp)',
            parsed.path,
            re.IGNORECASE,
        ))

    async def _embed_dlc_headers(self, urls: List[str]) -> Dict[str, str]:
        """Fetch bounded Steam bitmaps locally instead of letting the renderer request URLs."""
        if not self.session:
            return {}
        candidates = dict.fromkeys(url for url in urls if self._is_dlc_header_url(url))
        images: Dict[str, str] = {}
        semaphore = asyncio.Semaphore(8)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 6
        image_limit = 256 * 1024
        remaining_bytes = 4 * 1024 * 1024

        async def fetch(url: str) -> None:
            nonlocal remaining_bytes
            async with semaphore:
                time_left = deadline - loop.time()
                if time_left <= 0 or remaining_bytes <= 0:
                    return
                try:
                    async with self.session.get(
                        url, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=time_left),
                    ) as response:
                        mime = response.content_type
                        if response.status != 200 or mime not in ('image/jpeg', 'image/png', 'image/webp'):
                            return
                        if response.content_length is not None and response.content_length > image_limit:
                            return
                        content = bytearray()
                        async for chunk in response.content.iter_chunked(65536):
                            if len(content) + len(chunk) > image_limit:
                                return
                            content.extend(chunk)
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                    return
                if mime == 'image/jpeg':
                    valid = content.startswith(b'\xff\xd8\xff') and content.endswith(b'\xff\xd9')
                elif mime == 'image/png':
                    valid = content.startswith(b'\x89PNG\r\n\x1a\n') and content.endswith(b'IEND\xaeB`\x82')
                else:
                    valid = content.startswith(b'RIFF') and content[8:12] == b'WEBP'
                if valid and len(content) <= remaining_bytes:
                    remaining_bytes -= len(content)
                    images[url] = f'data:{mime};base64,' + base64.b64encode(content).decode('ascii')

        await asyncio.gather(*(fetch(url) for url in candidates))
        return images

    async def _get_dlc_market_list(self, dlc_type: int = 1) -> List[Dict]:
        if not self.session:
            raise NetworkException("插件未初始化，HTTP会话不可用")

        last_error: Optional[Exception] = None
        saw_valid_empty = False
        for base in self._api_bases():
            url = f"{base}/dlc/list?type={dlc_type}"
            logger.info(f"DLC列表: 请求 URL={url}")
            try:
                async with self.session.get(url, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                    logger.info(f"DLC列表: 响应 status={resp.status}, content-type={resp.headers.get('Content-Type')}")
                    if resp.status == 200:
                        data = await read_json(resp)
                        if isinstance(data, list):
                            items = data
                        elif isinstance(data, dict):
                            code = data.get('code')
                            try:
                                code_ok = code is None or int(code) == 200
                            except (TypeError, ValueError):
                                code_ok = False
                            payload = data.get('data') or data.get('response') or data.get('result')
                            items = payload if isinstance(payload, list) else []
                            if not code_ok:
                                items = []
                        else:
                            items = []
                        logger.info(f"DLC列表: 解析到 items_count={len(items)}")
                        if items:
                            return items
                        if isinstance(data, (list, dict)):
                            saw_valid_empty = True
                        last_error = ApiResponseException(f"DLC列表 API 源无有效数据: {base}")
                        logger.info(f"DLC列表: 源 {base} 无有效数据，尝试下一个源")
                        continue
                    logger.info(f"DLC列表: 源 {base} 返回状态码 {resp.status}，尝试下一个源")
                    last_error = ApiResponseException(f"DLC列表 API 返回错误状态码: {resp.status}")
            except aiohttp.ClientError as e:
                logger.error(f"DLC列表 API 网络请求失败 ({base}, aiohttp.ClientError): {e}")
                last_error = NetworkException("DLC列表 API 网络请求失败")
            except asyncio.TimeoutError:
                logger.error(f"请求 DLC列表 API 超时 ({base})")
                last_error = NetworkException("请求 DLC列表 API 超时")
            except ApiResponseException as e:
                last_error = e
            except Exception as e:
                logger.error(f"查询 DLC列表 时发生未知错误 ({base}): {e}", exc_info=True)
                last_error = NetworkException("查询 DLC列表 失败")

        if saw_valid_empty:
            return []
        if isinstance(last_error, NetworkException):
            raise last_error
        if isinstance(last_error, ApiResponseException):
            raise last_error
        raise NetworkException("查询 DLC列表 失败")

    async def tmpdlc_list(self, event: AstrMessageEvent):
        logger.info("DLC列表: 开始处理命令")
        try:
            items = await self._get_dlc_market_list(1)
        except Exception:
            yield event.plain_result("查询DLC列表失败")
            logger.error("DLC列表: 获取市场列表失败")
            return
        if not items:
            yield event.plain_result("暂无数据")
            logger.info("DLC列表: 无数据")
            return
        lines: List[str] = []
        for it in items:
            name = str(it.get('name') or '').strip()
            final_price = it.get('finalPrice')
            discount = it.get('discount') or 0
            price_str = ""
            try:
                if isinstance(final_price, (int, float)):
                    price_str = f"￥{int(final_price) // 100}"
            except Exception:
                price_str = ""
            if discount and isinstance(discount, (int, float)) and discount > 0:
                lines.append(f"{name} {price_str} (-{int(discount)}%)")
            else:
                lines.append(f"{name} {price_str}")
        text = "\n".join(lines)
        logger.info(f"DLC列表: 聚合文本长度={len(text)} 行数={len(lines)}")
        if self._cfg_bool('dlc_list_image', False):
            logger.info("DLC列表: 尝试进行图片渲染(html_render)")
            tmpl = """
<style>
  html, body { margin:0; padding:0; background:#222d33; width:auto; }
  * { box-sizing: border-box; }
</style>
<div style=\"width:100vw;background:#222d33;color:#fff;font-family:system-ui,Segoe UI,Helvetica,Arial,sans-serif;\">
  <div style=\"font-size:20px;font-weight:600;margin:0;padding:12px 0 8px 0;\">DLC 列表</div>
  {% for it in items %}
  <div style=\"display:flex;flex-direction:row;background:#24313a;margin:0 0 12px 0;padding:12px;\">
    {% if it.header_image %}<img src=\"{{ it.header_image|e }}\" style=\"width:210px;height:auto;object-fit:cover;\"/>{% endif %}
    <div style=\"flex:1;padding:0 12px;\">
      <div style=\"font-size:18px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;\">{{ it.name|e }}</div>
      <div style=\"font-size:14px;color:#e5e5e5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;text-overflow:ellipsis;\">{{ it.desc|e }}</div>
      <div style=\"margin-top:8px;\">
        <span style=\"display:inline-block;color:#BEEE11;font-size:16px;\">{{ it.price_str|e }}</span>
        {% if it.discount and it.discount > 0 %}
        <span style=\"display:inline-block;color:#cbcbcb;font-size:16px;text-decoration:line-through;margin-left:6px;\">{{ it.original_price_str|e }}</span>
        <span style=\"font-size:14px;color:#BEEE11;background:#4c6b22;padding:2px 6px;margin-left:4px;\">-{{ it.discount|e }}%</span>
        {% endif %}
      </div>
    </div>
  </div>
  {% endfor %}
</div>
"""
            headers = [str(it.get('headerImageUrl') or '').strip() for it in items]
            embedded_headers = await self._embed_dlc_headers(headers)
            mapped: List[Dict[str, Any]] = []
            for it, header in zip(items, headers):
                name = str(it.get('name') or '').strip()
                desc = str(it.get('desc') or '').strip()
                original = it.get('originalPrice')
                finalp = it.get('finalPrice')
                discount = it.get('discount') or 0
                def _p(v):
                    try:
                        return f"￥{int(v) // 100}" if isinstance(v, (int, float)) else ""
                    except Exception:
                        return ""
                mapped.append({
                    'name': name,
                    'desc': desc,
                    'header_image': embedded_headers.get(header, ''),
                    'price_str': _p(finalp),
                    'original_price_str': _p(original),
                    'discount': int(discount) if isinstance(discount, (int, float)) else 0
                })
            try:
                options = { 'type': 'jpeg', 'quality': 92, 'full_page': True, 'omit_background': False }
                url = await self.html_render(tmpl, { 'items': mapped }, options=options)
                if isinstance(url, str) and url:
                    logger.info(f"DLC列表: html_render 成功 -> {url}")
                    yield event.chain_result([Image.fromURL(url)])
                    return
                logger.error("DLC列表: html_render 返回空，尝试文本渲染")
            except Exception as e:
                logger.error(f"DLC列表: html_render 异常: {e}")
            img = await self._render_text_to_image(text)
            if isinstance(img, (bytes, bytearray)):
                logger.info("DLC列表: 文本渲染成功(字节)")
                yield event.chain_result([Image.fromBytes(img)])
                return
            if isinstance(img, str) and img.startswith('http'):
                logger.info(f"DLC列表: 文本渲染成功(URL={img})")
                yield event.chain_result([Image.fromURL(img)])
                return
            logger.error("DLC列表: 所有渲染失败，回退为文本")
        yield event.plain_result(text)

    async def tmpdlc_map_alias(self, event: AstrMessageEvent):
        async for r in self.tmpdlc_list(event):
            yield r
