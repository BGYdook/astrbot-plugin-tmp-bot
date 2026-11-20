"""Translation and localized formatting."""

import hashlib
import re
import secrets
import unicodedata
from typing import Optional, List, Dict, Tuple, Any

from .astrbot_compat import logger
from .shared import PLUGIN_ROOT, _cleanup_cn_location_text, read_json


_STATUS_SUFFIX = re.compile(r"\s*-\s*[A-Za-z]+(?: [A-Za-z]+)*\s*\(\d+\)\s*$")
_PLACE_SUFFIX = re.compile(r"\s*(?:\((city|location|road|port)\)|（(?:城市|地点)）)\s*$", re.IGNORECASE)
_LATIN_LETTERS = str.maketrans({"ø": "o", "ł": "l", "æ": "ae", "œ": "oe", "ð": "d", "þ": "th", "ı": "i"})
_HAN = re.compile(r"[\u3400-\u9fff]")
_NAME_CHARACTERS = str.maketrans({"’": "'", "‘": "'", "–": "-", "—": "-", "‑": "-"})


def _place_name(value: str) -> str:
    value = unicodedata.normalize("NFC", value).translate(_NAME_CHARACTERS).strip()
    return " ".join(_PLACE_SUFFIX.sub("", _STATUS_SUFFIX.sub("", value)).split())


def _place_key(value: str) -> str:
    folded = unicodedata.normalize("NFKD", _place_name(value).casefold().translate(_LATIN_LETTERS))
    return "".join(char for char in folded if not unicodedata.combining(char))


class TranslationMixin:
    COUNTRY_MAP_EN_TO_CN = {
        "germany": "德国",
        "de": "德国",
        "france": "法国",
        "fr": "法国",
        "united kingdom": "英国",
        "uk": "英国",
        "gb": "英国",
        "netherlands": "荷兰",
        "nl": "荷兰",
        "belgium": "比利时",
        "be": "比利时",
        "poland": "波兰",
        "pl": "波兰",
        "czech republic": "捷克",
        "czechia": "捷克",
        "cz": "捷克",
        "slovakia": "斯洛伐克",
        "sk": "斯洛伐克",
        "italy": "意大利",
        "it": "意大利",
        "spain": "西班牙",
        "es": "西班牙",
        "portugal": "葡萄牙",
        "pt": "葡萄牙",
        "switzerland": "瑞士",
        "ch": "瑞士",
        "austria": "奥地利",
        "at": "奥地利",
        "hungary": "匈牙利",
        "hu": "匈牙利",
        "denmark": "丹麦",
        "dk": "丹麦",
        "sweden": "瑞典",
        "se": "瑞典",
        "norway": "挪威",
        "no": "挪威",
        "finland": "芬兰",
        "fi": "芬兰",
        "estonia": "爱沙尼亚",
        "ee": "爱沙尼亚",
        "latvia": "拉脱维亚",
        "lv": "拉脱维亚",
        "lithuania": "立陶宛",
        "lt": "立陶宛",
        "russia": "俄罗斯",
        "ru": "俄罗斯",
        "turkey": "土耳其",
        "tr": "土耳其",
        "romania": "罗马尼亚",
        "ro": "罗马尼亚",
        "bulgaria": "保加利亚",
        "bg": "保加利亚",
        "greece": "希腊",
        "gr": "希腊",
        "united states": "美国",
        "usa": "美国",
        "us": "美国",
        "iceland": "冰岛",
        "is": "冰岛",
        "svalbard": "斯瓦尔巴群岛",
        "al": "阿尔巴尼亚",
        "ba": "波斯尼亚和黑塞哥维那",
        "hr": "克罗地亚",
        "ie": "爱尔兰",
        "lu": "卢森堡",
        "me": "黑山",
        "mk": "北马其顿",
        "rs": "塞尔维亚",
        "si": "斯洛文尼亚",
        "ua": "乌克兰",
        "xk": "科索沃",
        "ca": "加拿大",
        "canada": "加拿大",
        "bosnia-herzegovina": "波斯尼亚和黑塞哥维那",
        "macedonia": "北马其顿",
        "kazakshtan": "哈萨克斯坦",
        "saudi arabia": "沙特阿拉伯",
        "saudi arbia": "沙特阿拉伯",
        "westbank": "约旦河西岸",
        "åland": "奥兰群岛",
    }

    LANGUAGE_MAP_EN_TO_CN = {
        "english": "英语",
        "chinese (simplified)": "简体中文",
        "chinese (traditional)": "繁体中文",
        "french": "法语",
        "german": "德语",
        "russian": "俄语",
        "spanish": "西班牙语",
        "portuguese": "葡萄牙语",
        "italian": "意大利语",
        "polish": "波兰语",
        "czech": "捷克语",
        "slovak": "斯洛伐克语",
        "dutch": "荷兰语",
        "danish": "丹麦语",
        "swedish": "瑞典语",
        "norwegian": "挪威语",
        "finnish": "芬兰语",
        "estonian": "爱沙尼亚语",
        "latvian": "拉脱维亚语",
        "lithuanian": "立陶宛语",
        "romanian": "罗马尼亚语",
        "bulgarian": "保加利亚语",
        "greek": "希腊语",
        "hungarian": "匈牙利语",
        "turkish": "土耳其语",
        "ukrainian": "乌克兰语",
        "arabic": "阿拉伯语",
        "japanese": "日语",
        "korean": "韩语",
    }

    EVENT_TYPE_MAP_EN_TO_CN = {
        "convoy": "车队巡游",
        "truck_show_and_convoy": "卡车展与车队巡游",
        "truckfest and convoy": "卡车展与车队巡游",
        "truckfest": "卡车展",
        "truck show": "卡车展",
        "special event": "特别活动",
    }

    EVENT_LOCATION_MAP_EN_TO_CN = {
        "other": "其他",
        "city": "城市",
        "hotel": "酒店",
        "slots": "停车位",
        "booked slots": "预订停车位",
        "container port": "集装箱港口",
        "port": "港口",
        "ferry": "渡轮码头",
        "train station": "火车站",
        "service station": "维修站",
        "gas station": "加油站",
        "fuel station": "加油站",
        "rest area": "休息区",
        "truck stop": "卡车停靠站",
        "parking lot": "停车场",
        "garage": "车库",
        "quarry": "采石场",
        "intersection": "交叉口",
        "junction": "交汇处",
        "tunnel": "隧道",
        "tunnels": "隧道",
        "race track": "赛车场",
        "any city in the play area": "游戏区域内任意城市",
        "to be determined": "待定",
    }

    COMMON_TEXT_MAP_EN_TO_CN = {
        "truck show and convoy": "卡车展与车队巡游",
        "truckfest and convoy": "卡车展与车队巡游",
        "any city in the play area": "游戏区域内任意城市",
        "to be determined": "待定",
        "booked slots": "预订停车位",
        "container port": "集装箱港口",
        "join our rules": "加入规则",
        "join rules": "加入规则",
        "how to contact us": "联系方式",
        "truck show": "卡车展",
        "truckfest": "卡车展",
        "convoy": "车队巡游",
    }

    CITY_MAP_EN_TO_CN = {
        "calais": "加来",
        "köln": "科隆",
        "münchen": "慕尼黑",
        "nürnberg": "纽伦堡",
        "warszawa": "华沙",
        "wien": "维也纳",
        "roma": "罗马",
        "firenze": "佛罗伦萨",
        "venezia": "威尼斯",
        "göteborg": "哥德堡",
        "københavn": "哥本哈根",
        "athína": "雅典",
        "odessa": "敖德萨",
        "duisburg": "杜伊斯堡",
        "berlin": "柏林",
        "paris": "巴黎",
        "london": "伦敦",
        "cambridge": "剑桥",
        "milano": "米兰",
        "milan": "米兰",
        "rome": "罗马",
        "madrid": "马德里",
        "barcelona": "巴塞罗那",
        "lisbon": "里斯本",
        "rotterdam": "鹿特丹",
        "amsterdam": "阿姆斯特丹",
        "brussels": "布鲁塞尔",
        "prague": "布拉格",
        "vienna": "维也纳",
        "budapest": "布达佩斯",
        "warsaw": "华沙",
        "krakow": "克拉科夫",
        "akureyri": "阿克雷里",
        "burgos": "布尔戈斯",
        "praha": "布拉格",
        "steinkjer": "斯泰恩谢尔",
        "valmiera": "瓦尔米耶拉",
        "umeå": "于默奥",
        "umea": "于默奥",
        "longyearbyen": "朗伊尔城",
        "napoli": "那不勒斯",
        "sundsvall": "松兹瓦尔",
        "frankfurt am main": "法兰克福",
        "frankfurt": "法兰克福",
        "bremen": "不来梅",
        "hamburg": "汉堡",
        "munich": "慕尼黑",
        "nuremberg": "纽伦堡",
        "hanover": "汉诺威",
        "hannover": "汉诺威",
        "rostock": "罗斯托克",
        "athens": "雅典",
        "kavala": "卡瓦拉",
        "lamia": "拉米亚",
        "aarhus": "奥胡斯",
        "gävle": "耶夫勒",
        "gavle": "耶夫勒",
        "pärnu": "派尔努",
        "parnu": "派尔努",
        "vaasa": "瓦萨",
        "poznań": "波兹南",
        "poznan": "波兹南",
        "salzburg": "萨尔茨堡",
        "travemünde": "特拉弗明德",
        "travemunde": "特拉弗明德",
        "eindhoven": "埃因霍温",
        "bern": "伯尔尼",
        "innsbruck": "因斯布鲁克",
        "klagenfurt am wörthersee": "克拉根福",
        "klagenfurt": "克拉根福",
        "liepāja": "利耶帕亚",
        "liepaja": "利耶帕亚",
        "narva": "纳尔瓦",
        "rijeka": "里耶卡",
        "szeged": "塞格德",
        "tirana": "地拉那",
        "istanbul": "伊斯坦布尔",
        "i̇stanbul": "伊斯坦布尔",
        "omaha": "奥马哈",
        "nogales": "诺加莱斯",
        "scottsbluff": "斯科茨布拉夫",
        "show low": "肖洛",
        "wenatchee": "韦纳奇",
        "yakima": "亚基马",
    }

    LOCATION_FIX_MAP = {
        "kirkenes": "希尔克内斯",
        "kirkenes quarry": "希尔克内斯 采石场",
        "c-d road": "加莱-杜伊斯堡",
        "cd road": "加莱-杜伊斯堡",
        "calais-duisburg road": "加莱-杜伊斯堡",
        "calais - duisburg": "加莱-杜伊斯堡",
        "calais–duisburg": "加莱-杜伊斯堡",
        "calais-duisburg": "加莱-杜伊斯堡",
        "calais intersection": "加来 交叉口",
        "dortmund": "多特蒙德",
        "hannover": "汉诺威",
        "hamburg": "汉堡",
        "strasbourg": "斯特拉斯堡",
        "dijon": "第戎",
        "reims": "兰斯",
        "brussel": "布鲁塞尔",
        "aalborg": "奥尔堡",
        "kiruna": "基律纳",
        "skellefteå": "谢莱夫特奥",
        "skelleftea": "谢莱夫特奥",
        "ljubjana": "卢布尔雅那",
        "ljubljana": "卢布尔雅那",
        "nikel": "尼克尔",
        "travemünde": "特拉弗明德",
        "travemunde": "特拉弗明德",
        "zürich": "苏黎世",
        "zurich": "苏黎世",
        "alpen road": "阿尔卑斯公路",
        "channel tunnel": "英吉利海峡隧道",
        "folkestone": "福克斯通",
    }

    async def _translate_text(self, content: str, cache: bool = True) -> str:
        s = (content or "").strip()
        if not s:
            return content
        if not self._cfg_bool('baidu_translate_enable', True):
            return content
        use_cache = self._cfg_bool('baidu_translate_cache_enable', False)
        cache_key = hashlib.md5(s.encode('utf-8'), usedforsecurity=False).hexdigest()
        if cache and use_cache:
            cached = self._translate_cache.get(cache_key)
            if cached:
                return cached
        app_id = self._cfg_str('baidu_translate_app_id', '').strip()
        app_key = self._cfg_str('baidu_translate_key', '').strip()
        if not app_id or not app_key or not self.session:
            return content
        try:
            salt = str(secrets.randbelow(9000) + 1000)
            sign = hashlib.md5((app_id + s + salt + app_key).encode('utf-8'), usedforsecurity=False).hexdigest()
            url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
            params = {
                'q': s,
                'from': 'auto',
                'to': 'zh',
                'appid': app_id,
                'salt': salt,
                'sign': sign
            }
            async with self.session.get(url, params=params, timeout=self._cfg_int('api_timeout_seconds', 10)) as resp:
                if resp.status == 200:
                    data = await read_json(resp)
                    if isinstance(data, dict) and data.get('trans_result'):
                        dst = data['trans_result'][0].get('dst')
                        if isinstance(dst, str) and dst.strip():
                            translated = dst.strip()
                            if cache and use_cache:
                                self._translate_cache[cache_key] = translated
                            return translated
        except Exception:
            return content
        return content

    def _load_location_maps(self) -> None:
        if getattr(self, "_location_maps_loaded", False):
            return

        countries = {_place_key(name): cn for name, cn in self.COUNTRY_MAP_EN_TO_CN.items()}
        cities = {_place_key(name): cn for name, cn in self.CITY_MAP_EN_TO_CN.items()}
        places = {}
        city_aliases = {}
        data_dir = PLUGIN_ROOT / "TruckersMP-citties-name"
        for filename in ("s1-cities.md", "promods-cities.md", "ats-cities.md"):
            path = data_dir / filename
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError) as exc:
                logger.warning(f"加载地点词库失败 {filename}: {exc}")
                continue
            for line in lines:
                if not line.startswith("|"):
                    continue
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if len(cells) != 2:
                    continue
                source, target = cells
                name = _place_key(source)
                cn = _place_name(target)
                if not name or not _HAN.search(cn):
                    continue
                kind = _PLACE_SUFFIX.search(_STATUS_SUFFIX.sub("", source))
                if kind and kind[1].lower() == "city":
                    cities[name] = cn
                    for alias in name.split("/"):
                        city_aliases.setdefault(alias.strip(), cn)
                elif kind:
                    places[name] = cn
                else:
                    countries[name] = cn

        for alias, cn in city_aliases.items():
            cities.setdefault(alias, cn)
        for name, cn in self.LOCATION_FIX_MAP.items():
            places.setdefault(_place_key(name), cn)
        self.COUNTRY_MAP_EN_TO_CN = countries
        self.CITY_MAP_EN_TO_CN = cities
        self.LOCATION_FIX_MAP = places
        self._location_maps_loaded = True

    async def _translate_country_city(self, country: Optional[str], city: Optional[str]) -> Tuple[str, str]:
        country_name = _place_name(country or "")
        city_name = _place_name(city or "")
        country_key = _place_key(country_name)
        country_cn = self.COUNTRY_MAP_EN_TO_CN.get(country_key, "")
        city_key = _place_key(city_name)
        city_cn = self.CITY_MAP_EN_TO_CN.get(city_key) or self.LOCATION_FIX_MAP.get(city_key)

        if city_name and not city_cn:
            # Location data sometimes embeds a country prefix, including a translated prefix.
            parts = re.split(r"\s*[-,]\s*", city_name, maxsplit=1)
            if len(parts) == 2:
                prefix_key = _place_key(parts[0])
                prefix_cn = self.COUNTRY_MAP_EN_TO_CN.get(prefix_key)
                if prefix_cn or (country_key and prefix_key == country_key):
                    city_name = parts[1]
                    country_cn = country_cn or prefix_cn or ""
            elif country_name:
                prefix = re.match(re.escape(country_name) + r"\s+", city_name, re.IGNORECASE)
                if prefix:
                    city_name = city_name[prefix.end():]
            city_key = _place_key(city_name)
            city_cn = self.CITY_MAP_EN_TO_CN.get(city_key) or self.LOCATION_FIX_MAP.get(city_key)

        if country_name and not country_cn:
            country_cn = await self._translate_text(country_name, cache=True)
        if city_name and not city_cn:
            city_cn = await self._translate_text(city_name, cache=True)
        if _HAN.search(country_cn or ""):
            country_cn = _cleanup_cn_location_text(country_cn)
        return country_cn or country_name, city_cn or city_name

    async def _translate_traffic_name(self, name: Optional[str]) -> str:
        s = _place_name(name or "")
        if not s:
            return s
        key = _place_key(s)

        # 1. 查修正表
        fix = self.LOCATION_FIX_MAP.get(key)
        if fix:
            return fix

        # 2. 查城市表 (路况里的 name 经常是城市名)
        city_fix = self.CITY_MAP_EN_TO_CN.get(key)
        if city_fix:
            return city_fix

        suffixes = ("intersection", "quarry", "junction", "port", "ferry", "tunnel", "tunnels", "truck stop", "rest area")
        m_suffix = re.fullmatch(r"(?P<base>.+?)\s+(?P<suffix>" + "|".join(suffixes) + ")", s, re.IGNORECASE)
        if m_suffix:
            base = (m_suffix.group("base") or "").strip()
            suffix = (m_suffix.group("suffix") or "").strip().lower()
            base_cn = await self._translate_traffic_name(base)
            suffix_cn = self.EVENT_LOCATION_MAP_EN_TO_CN[suffix]
            if base_cn and base_cn != base:
                return f"{base_cn} {suffix_cn}".strip()

        for sep in (" - ", "–", "-", "/"):
            if sep in s:
                parts = [p.strip() for p in s.split(sep) if p.strip()]
                if len(parts) >= 2:
                    translated_parts: List[str] = []
                    for p in parts:
                        pk = _place_key(p)
                        translated_parts.append(
                            self.LOCATION_FIX_MAP.get(pk)
                            or self.CITY_MAP_EN_TO_CN.get(pk)
                            or p
                        )
                    joiner = " - " if sep.strip() in ("-", "–") else sep
                    if translated_parts != parts:
                        return joiner.join(translated_parts)

        # 3. 百度翻译
        translated = await self._translate_text(s, cache=True)
        if translated:
            return translated
        return s

    @classmethod
    def _clean_tmp_text(cls, value: Any, limit: int = 1000) -> str:
        text = str(value or '').strip()
        if not text:
            return ''
        text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = re.sub(r'[#*_>`]+', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        for source, target in cls.COMMON_TEXT_MAP_EN_TO_CN.items():
            text = re.sub(
                r'(?<![A-Za-z])' + re.escape(source) + r'(?![A-Za-z])',
                target,
                text,
                flags=re.IGNORECASE,
            )
        if len(text) > limit:
            return text[:limit].rstrip() + '…'
        return text

    @classmethod
    def _translate_language(cls, value: Any) -> str:
        raw = str(value or '').strip()
        return cls.LANGUAGE_MAP_EN_TO_CN.get(raw.lower(), raw or '未知')

    @classmethod
    def _translate_event_type(cls, event_type: Dict[str, Any]) -> str:
        if not isinstance(event_type, dict):
            return '未知'
        for key in (event_type.get('name'), event_type.get('key')):
            raw = str(key or '').strip()
            if not raw:
                continue
            translated = cls.EVENT_TYPE_MAP_EN_TO_CN.get(raw.lower())
            if translated:
                return translated
        return str(event_type.get('name') or event_type.get('key') or '未知')

    def _format_event_place(self, place: Any) -> str:
        if not isinstance(place, dict):
            return ''
        city = str(place.get('city') or '').strip()
        location = str(place.get('location') or '').strip()
        if city:
            city_key = _place_key(city)
            city = (
                self.CITY_MAP_EN_TO_CN.get(city_key)
                or self.LOCATION_FIX_MAP.get(city_key)
                or self.EVENT_LOCATION_MAP_EN_TO_CN.get(city_key)
                or city
            )
        if location:
            location_key = _place_key(location)
            location = (
                self.EVENT_LOCATION_MAP_EN_TO_CN.get(location_key)
                or self.LOCATION_FIX_MAP.get(location_key)
                or self.CITY_MAP_EN_TO_CN.get(location_key)
                or location
            )
        if city and location and city.lower() != location.lower():
            return f"{city} · {location}"
        return city or location

    def _format_event_route(self, event_data: Dict[str, Any]) -> str:
        departure = self._format_event_place(event_data.get('departure'))
        arrival = self._format_event_place(event_data.get('arrive'))
        if departure and arrival:
            return f"{departure} → {arrival}"
        return departure or arrival or '未提供'
