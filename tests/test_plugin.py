"""Regression checks for the split plugin, without external APIs or chat adapters."""

import asyncio
import importlib
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "_tmp_bot_under_test"
package = ModuleType(PACKAGE_NAME)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE_NAME] = package
runtime_root = tempfile.TemporaryDirectory(prefix="tmp-bot-test-runtime-")
unittest.addModuleCleanup(runtime_root.cleanup)
with patch.dict("os.environ", {"ASTRBOT_ROOT": runtime_root.name}):
    plugin_module = importlib.import_module(f"{PACKAGE_NAME}.main")
    compat = importlib.import_module(f"{PACKAGE_NAME}.features.astrbot_compat")
    shared = importlib.import_module(f"{PACKAGE_NAME}.features.shared")

is_safe_http_url = shared.is_safe_http_url
read_json = shared.read_json


class FakeEvent:
    def __init__(self, text, segments=()):
        self.message_str = text
        self.message_obj = SimpleNamespace(message=segments)

    def get_self_id(self):
        return "bot"

    def get_sender_id(self):
        return "sender"

    def plain_result(self, text):
        return text


async def collect(results):
    return [result async for result in results]


class PluginTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        data_dir = tempfile.TemporaryDirectory()
        self.addCleanup(data_dir.cleanup)
        data_path_patch = patch.object(compat.StarTools, "get_data_dir", return_value=data_dir.name)
        data_path_patch.start()
        self.addCleanup(data_path_patch.stop)
        self.plugin = plugin_module.TmpBotPlugin(
            SimpleNamespace(), {"tmp_update_check_enable": False}
        )

    async def test_decorated_and_general_routes_reply_once_in_either_order(self):
        for first, second in (
            (self.plugin.cmd_tmp_help, self.plugin._on_any_message_dispatch),
            (self.plugin._on_any_message_dispatch, self.plugin.cmd_tmp_help),
        ):
            event = FakeEvent("／ 菜单")
            self.assertIn("TMP查询姬指令菜单", (await collect(first(event)))[0])
            self.assertEqual(await collect(second(event)), [])

    async def test_routing_supports_mentions_without_matching_regular_chat(self):
        mention = {"type": "at", "data": {"qq": "recipient"}}
        event = FakeEvent("查询 @recipient", [mention])
        self.assertEqual(self.plugin._match_command(event.message_str, event), "tmpquery")
        event = FakeEvent("定位服务有没有问题 @recipient", [mention])
        self.assertEqual(await collect(self.plugin._on_any_message_dispatch(event)), [])

    async def test_location_cache_waits_for_first_refresh(self):
        requested = asyncio.Event()
        ready = asyncio.Event()
        player = {"MpId": 42}

        async def read_snapshot():
            requested.set()
            await ready.wait()
            return {"players": [player]}

        response = SimpleNamespace(status=200, json=read_snapshot)
        session = MagicMock()
        session.get.return_value.__aenter__.return_value = response
        self.plugin.session = session

        first = asyncio.create_task(self.plugin._fetch_fullmap())
        await asyncio.wait_for(requested.wait(), timeout=1)
        second = asyncio.create_task(self.plugin._fetch_fullmap())
        await asyncio.sleep(0)
        try:
            self.assertFalse(second.done())
        finally:
            ready.set()
            await asyncio.wait_for(asyncio.gather(first, second), timeout=1)

        session.get.assert_called_once()
        self.assertEqual(self.plugin._get_fullmap_player("42"), player)
        self.plugin._fullmap_cache_ts = time.monotonic() - 301
        self.assertIsNone(self.plugin._get_fullmap_player("42"))

    async def test_lifecycle_reuses_session_and_closes_it(self):
        await self.plugin.initialize()
        session = self.plugin.session
        try:
            await self.plugin.initialize()
            self.assertIs(self.plugin.session, session)
        finally:
            await self.plugin.terminate()
        self.assertTrue(session.closed)
        self.assertIsNone(self.plugin.session)

    async def test_city_tables_load_and_existing_binding_format_remains_readable(self):
        self.assertEqual(self.plugin.CITY_MAP_EN_TO_CN.get("cologne"), "科隆")
        Path(self.plugin.bind_file).write_text('{"sender":"42"}', encoding="utf-8")
        self.assertEqual(self.plugin._get_bound_tmp_id("sender"), "42")
        self.assertTrue(self.plugin._bind_tmp_id("sender", "43", "Driver"))
        self.assertEqual(self.plugin._get_bound_tmp_id("sender"), "43")

    async def test_offline_location_dictionary_is_shared_by_commands(self):
        with patch.object(self.plugin, "_translate_text", AsyncMock(side_effect=lambda text, **_: text)) as external:
            self.assertEqual(
                await self.plugin._translate_country_city("Norway", "Norway - Svolvaer (City) - Low (1)"),
                ("挪威", "斯沃尔韦尔"),
            )
            self.assertEqual(await self.plugin._translate_country_city("Finland", "Joensuu"), ("芬兰", "约恩苏"))
            self.assertEqual(await self.plugin._translate_traffic_name("Kirkenes Quarry (Road)"), "希尔克内斯采石场")
            self.assertEqual(await self.plugin._translate_traffic_name("Calais Ferry (Port)"), "加来渡轮码头")
            self.assertEqual(
                self.plugin._format_event_route({
                    "departure": {"city": "Köln", "location": "Truck stop"},
                    "arrive": {"city": "Coeur d’Alene"},
                }),
                "科隆 · 卡车停靠站 → 科达伦",
            )
            external.assert_not_awaited()
            self.assertEqual(await self.plugin._translate_country_city(None, "Unlisted Depot"), ("", "Unlisted Depot"))

    async def test_external_targets_and_json_bodies_are_bounded(self):
        self.assertFalse(is_safe_http_url("https://127.0.0.1/private"))
        self.assertFalse(is_safe_http_url("https://224.0.0.1/data"))
        self.assertFalse(is_safe_http_url("https://example.com:invalid/data"))
        self.assertTrue(is_safe_http_url("http://localhost:8000", allow_local_http=True))
        self.assertFalse(is_safe_http_url("https://user:pass@example.com/data"))
        self.assertTrue(is_safe_http_url("https://api.example.com/data"))
        self.plugin._fullmap_cache = {
            "players": [],
            "tileUrl": "https://127.0.0.1/{z}/{x}/{y}.png",
        }
        self.assertIsNone(self.plugin._get_fullmap_tile_url("ets"))
        self.plugin._fullmap_cache["tileUrl"] = "https://map-cdn.krashnz.com/ets2map/ets2/v1.62/{z}/{x}/{y}.png"
        self.assertIn("map-cdn.krashnz.com", self.plugin._get_fullmap_tile_url("ets"))

        class Body:
            content_length = 4
            async def read(self):
                return b"{}"

        self.assertEqual(await read_json(Body()), {})
        with self.assertRaises(ValueError):
            await read_json(Body(), limit=1)

    async def test_configured_paths_and_urls_are_bounded(self):
        escaped = self.plugin.__class__(
            SimpleNamespace(),
            {"bind_file": "../../outside.json", "tmp_update_check_enable": False},
        )
        self.assertEqual(Path(escaped.bind_file).parent, Path(self.plugin.bind_file).parent)
        self.assertEqual(self.plugin._tile_url("ets", "https://default.test/{z}/{x}/{y}.png"), "https://default.test/{z}/{x}/{y}.png")
        escaped.config["extra_tile_ets_url"] = "http://169.254.169.254/{z}/{x}/{y}.png"
        self.assertEqual(escaped._tile_url("ets", "https://default.test/{z}/{x}/{y}.png"), "https://default.test/{z}/{x}/{y}.png")
        self.assertEqual(escaped._normalize_avatar_url("https://example.com/avatar.png"), None)

    async def test_vtc_history_returns_at_most_ten_entries(self):
        records = [{"name": f"VTC #{index:02}"} for index in range(1, 13)]
        with (
            patch.object(self.plugin, "_get_player_info", AsyncMock(return_value={})),
            patch.object(self.plugin, "_get_vtc_history", AsyncMock(return_value=records)),
        ):
            result, = await collect(self.plugin.tmpvtc_history(FakeEvent("历史车队 42")))
        self.assertIn("VTC #10", result)
        self.assertNotIn("VTC #11", result)
        self.assertIn("共 12 条记录", result)


if __name__ == "__main__":
    unittest.main()
