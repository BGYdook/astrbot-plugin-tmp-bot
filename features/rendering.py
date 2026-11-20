"""Shared text-to-image rendering."""

import json
import os
from pathlib import Path
from typing import Optional, Any


from .astrbot_compat import logger
from .shared import PLUGIN_ROOT, is_safe_http_url, read_response_bytes


class RenderingMixin:
    async def _render_text_to_image(self, text: str) -> Optional[Any]:
        if not self.session:
            return None
        # 读取 AstrBot 系统配置 data/cmd_config.json 的 t2i_endpoint/t2i_strategy
        url = None
        try:
            root = Path(os.environ.get('ASTRBOT_ROOT') or PLUGIN_ROOT.parent)
            cfg = root / 'data' / 'cmd_config.json'
            if os.path.exists(cfg):
                with open(cfg, 'r', encoding='utf-8') as f:
                    j = json.load(f)
                strategy = str(j.get('t2i_strategy') or '').strip()
                endpoint = str(j.get('t2i_endpoint') or '').strip()
                if strategy == 'remote' and endpoint and is_safe_http_url(endpoint, allow_local_http=True):
                    e = endpoint.rstrip('/')
                    url = e + "/text2img/generate"
                    logger.info("T2I: 使用系统配置的远程渲染服务")
        except Exception as e:
            logger.error(f"T2I: 读取系统配置失败: {e}")
        if not url:
            # 环境变量兜底
            endpoint = str(os.environ.get('ASTRBOT_T2I_ENDPOINT') or '').strip()
            if endpoint and is_safe_http_url(endpoint, allow_local_http=True):
                e = endpoint.rstrip('/')
                url = e + "/text2img/generate"
                logger.info("T2I: 使用环境变量配置的远程渲染服务")
        if not url:
            logger.info("T2I: 未找到远程服务地址，跳过图片渲染")
            return None
        payload = {
            'text': text
        }
        try:
            if len(text) > 20000:
                logger.warning("T2I: 输入文本超过长度限制")
                return None
            async with self.session.post(url, json=payload, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                logger.info(f"T2I: body_len={len(text)} status={resp.status} ct={resp.headers.get('Content-Type')}")
                ct = resp.headers.get('Content-Type', '')
                raw = await read_response_bytes(resp, 12 * 1024 * 1024)
                if 'application/json' in ct:
                    try:
                        data = json.loads(raw)
                    except Exception as je:
                        logger.error(f"T2I: JSON解析失败: {je}")
                        return None
                    img_b64 = (
                        data.get('image')
                        or (data.get('data') or {}).get('image')
                    )
                    img_url = (
                        data.get('url')
                        or (data.get('output')[0] if isinstance(data.get('output'), list) and data.get('output') else None)
                    )
                    if img_b64:
                        try:
                            import base64 as _b64
                            if len(img_b64) > 16 * 1024 * 1024:
                                return None
                            return _b64.b64decode(img_b64, validate=True)
                        except Exception:
                            logger.error("T2I: Base64解码失败")
                            return None
                    if img_url and is_safe_http_url(str(img_url)):
                        return str(img_url)
                    return None
                else:
                    content = raw
                    if content:
                        return content
                    return None
        except Exception as e:
            logger.error(f"文本转图片渲染失败: {e}", exc_info=True)
            return None
