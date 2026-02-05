"""
DLC 列表功能
"""

from typing import Any, Dict, List


async def tmpdlc_list(self, event, logger, Image, dlc_list_template):
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
        name = str(it.get("name") or "").strip()
        final_price = it.get("finalPrice")
        discount = it.get("discount") or 0
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
    if self._cfg_bool("dlc_list_image", False):
        logger.info("DLC列表: 尝试进行图片渲染(html_render)")
        tmpl = dlc_list_template()
        mapped: List[Dict[str, Any]] = []
        for it in items:
            name = str(it.get("name") or "").strip()
            desc = str(it.get("desc") or "").strip()
            header = str(it.get("headerImageUrl") or "").strip()
            original = it.get("originalPrice")
            finalp = it.get("finalPrice")
            discount = it.get("discount") or 0

            def _p(v):
                try:
                    return f"￥{int(v) // 100}" if isinstance(v, (int, float)) else ""
                except Exception:
                    return ""

            mapped.append(
                {
                    "name": name,
                    "desc": desc,
                    "headerImageUrl": header,
                    "price_str": _p(finalp),
                    "original_price_str": _p(original),
                    "discount": int(discount) if isinstance(discount, (int, float)) else 0,
                }
            )
        try:
            options = {"type": "jpeg", "quality": 92, "full_page": True, "omit_background": False}
            url = await self.html_render(tmpl, {"items": mapped}, options=options)
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
        if isinstance(img, str) and img.startswith("http"):
            logger.info(f"DLC列表: 文本渲染成功(URL={img})")
            yield event.chain_result([Image.fromURL(img)])
            return
        logger.error("DLC列表: 所有渲染失败，回退为文本")
    yield event.plain_result(text)


async def tmpdlc_map_alias(self, event, logger, Image, dlc_list_template):
    async for r in tmpdlc_list(self, event, logger, Image, dlc_list_template):
        yield r
