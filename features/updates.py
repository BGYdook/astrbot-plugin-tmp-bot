"""TruckersMP plugin version checks and group notifications."""

import asyncio
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from .shared import read_json
from .astrbot_compat import AstrMessageEvent, MessageEventResult, logger


class UpdateMixin:
    TMP_VERSION_API = "https://api.truckersmp.com/v2/version"

    TMP_UPDATE_MAX_NOTIFY_ATTEMPTS = 10

    @staticmethod
    def _as_config_bool(value: Any, default: bool) -> bool:
        """更宽容地解析布尔配置（兼容 WebUI 传入的 "true"/"false" 字符串）。"""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            s = value.strip().lower()
            if s in ("1", "true", "yes", "on", "是", "开启", "启用"):
                return True
            if s in ("0", "false", "no", "off", "否", "关闭", "禁用"):
                return False
        return default

    def _tmp_update_enabled(self) -> bool:
        return self._as_config_bool(self.config.get('tmp_update_check_enable', True), True)

    def _tmp_update_notify_first_run(self) -> bool:
        return self._as_config_bool(self.config.get('tmp_update_notify_first_run', False), False)

    def _tmp_update_interval_seconds(self) -> int:
        try:
            minutes = int(self.config.get('tmp_update_check_interval_minutes', 30))
        except Exception:
            minutes = 30
        if minutes < 5:
            minutes = 5
        return minutes * 60

    def _tmp_update_send_delay(self) -> float:
        try:
            delay = float(self.config.get('tmp_update_send_delay_seconds', 2))
        except Exception:
            delay = 2.0
        return min(max(delay, 0.0), 30.0)

    def _parse_tmp_update_excludes(self) -> set:
        """解析「不接收更新通知的群号」，支持中英文逗号、空格、换行分隔。"""
        raw = self._cfg_str('tmp_update_exclude_groups', '')
        raw = re.sub(r"#[^\n]*", "", raw)
        excludes = set()
        for chunk in re.split(r"[,，;；\s]+", raw):
            item = chunk.strip()
            if not item or item.startswith('#'):
                continue
            if item.startswith('群') and item[1:].isdigit():
                item = item[1:]
            excludes.add(item)
        return excludes

    @staticmethod
    def _tmp_update_origin_group_id(origin: str) -> str:
        parts = str(origin).split(':')
        if len(parts) >= 3:
            return parts[2].split('_')[-1]
        return ''

    @staticmethod
    def _tmp_update_group_key(origin: str, info: Dict[str, str]) -> str:
        """同一平台的同一个群共用发送记录，不受成员隔离会话等前缀影响。"""
        platform_id = origin.split(':', 1)[0]
        parts = origin.split(':', 2)
        group_id = str(info.get('group_id') or (parts[2] if len(parts) == 3 else ''))
        return f"{platform_id}:GroupMessage:{group_id}"

    @staticmethod
    def _tmp_version_key(snapshot: Optional[Dict[str, Any]]) -> Tuple[str, str, str]:
        if not isinstance(snapshot, dict):
            return ("", "", "")
        return (
            str(snapshot.get('name') or ''),
            str(snapshot.get('ets2') or ''),
            str(snapshot.get('ats') or ''),
        )

    @staticmethod
    def _tmp_major_minor(version: str) -> str:
        """提取 1.61.3.18s 这类版本号的主次版本（1.61）。"""
        m = re.match(r"^\s*(\d+)\.(\d+)", str(version or ""))
        return f"{m.group(1)}.{m.group(2)}" if m else ""

    @classmethod
    def _format_tmp_update_message(cls, snapshot: Dict[str, Any]) -> str:
        version = str(snapshot.get('name') or '未知')
        official_data = snapshot.get('official')
        if isinstance(official_data, dict):
            official_ets2_raw = str(official_data.get('ets2') or '').strip()
        else:
            # Backward compatibility with update state saved by older versions.
            official_ets2_raw = str(official_data or '').strip()
        official_ets2 = official_ets2_raw or '未知'
        ets2 = str(snapshot.get('ets2') or '未知')
        ats = str(snapshot.get('ats') or '未知')

        if official_ets2 == '未知':
            ets2_ok = '未知'
        else:
            # 欧卡：官方 Steam 版本必须与 TMP 支持的版本完全一致
            ets2_ok = '✅' if ets2 != '未知' and official_ets2_raw == ets2 else '❌'
        if official_ets2 == '未知':
            ats_ok = '未知'
        else:
            # ATS shares the major/minor game release with ETS2.
            ats_mm = cls._tmp_major_minor(official_ets2_raw)
            supported_ats_mm = cls._tmp_major_minor(ats)
            ats_ok = '✅' if ats != '未知' and ats_mm and ats_mm == supported_ats_mm else '❌'

        return (
            "检测到联机插件有更新!\n"
            f"联机插件版本: {version}\n"
            f"支持欧卡版本: {ets2}\n"
            f"支持美卡版本: {ats}\n"
            "-----------------------------\n"
            f"📊 官方Steam版本: {official_ets2}\n"
            f"🎮 欧卡兼容: {ets2_ok}\n"
            f"🎮 美卡兼容: {ats_ok}"
        )

    def _load_tmp_update_state(self) -> None:
        self._tmp_update_state = {}
        self._tmp_update_groups = {}
        try:
            if os.path.exists(self._tmp_update_state_file):
                if os.path.getsize(self._tmp_update_state_file) > 2 * 1024 * 1024:
                    raise ValueError('更新状态文件超过大小限制')
                with open(self._tmp_update_state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._tmp_update_state = data
        except Exception as e:
            logger.error(f"读取联机插件更新状态失败: {e}")

        groups = self._tmp_update_state.get('groups')
        if isinstance(groups, dict):
            for origin, info in groups.items():
                if not isinstance(origin, str) or not isinstance(info, dict):
                    continue
                group_id = str(info.get('group_id') or self._tmp_update_origin_group_id(origin) or '')
                if not group_id:
                    continue
                self._tmp_update_groups[origin] = {
                    'platform_id': str(info.get('platform_id') or origin.split(':', 1)[0]),
                    'group_id': group_id,
                    'name': str(info.get('name') or ''),
                }

        last = self._tmp_update_state.get('last_snapshot')
        if isinstance(last, dict) and last.get('name'):
            logger.info(
                "联机插件版本基线: "
                f"{last.get('name')}（欧卡 {last.get('ets2') or '未知'} / 美卡 {last.get('ats') or '未知'}）"
            )

    def _save_tmp_update_state(self) -> None:
        try:
            self._tmp_update_state['schema'] = 1
            self._tmp_update_state['groups'] = self._tmp_update_groups
            directory = os.path.dirname(self._tmp_update_state_file)
            if directory:
                os.makedirs(directory, exist_ok=True)
            tmp_path = self._tmp_update_state_file + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self._tmp_update_state, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._tmp_update_state_file)
        except Exception as e:
            logger.error(f"保存联机插件更新状态失败: {e}")

    def _remember_tmp_update_group(self, event: Any) -> None:
        """从收到的群消息中记录群会话，作为 OneBot 群列表接口不可用时的兜底。"""
        try:
            get_platform_name = getattr(event, 'get_platform_name', None)
            if callable(get_platform_name) and get_platform_name() == 'discord':
                return
            get_group_id = getattr(event, 'get_group_id', None)
            group_id = get_group_id() if callable(get_group_id) else ''
            if not group_id:
                return
            origin = str(getattr(event, 'unified_msg_origin', '') or '')
            if not origin:
                session = getattr(event, 'session', None)
                if session is not None:
                    origin = str(session)
            if not origin:
                return
            platform_id = ''
            get_platform_id = getattr(event, 'get_platform_id', None)
            if callable(get_platform_id):
                platform_id = str(get_platform_id() or '')
            info = {
                'platform_id': platform_id or origin.split(':', 1)[0],
                'group_id': str(group_id),
                'name': str((self._tmp_update_groups.get(origin) or {}).get('name') or ''),
            }
            self._tmp_update_groups[origin] = info
        except Exception as exc:
            logger.debug(f"记录更新通知群组失败: {exc}")

    async def _discover_tmp_update_groups(self) -> Dict[str, Dict[str, str]]:
        """获取需要推送的群会话。

        优先使用 aiocqhttp(OneBot) 的 get_group_list（能拿到机器人所在的全部群），
        同时合并从历史消息中记录到的群；如果某个平台能成功拉到群列表，则以实时列表为准，
        避免机器人退群后仍向旧群重试。
        """
        known: Dict[str, Dict[str, str]] = {}
        for origin, info in self._tmp_update_groups.items():
            if origin and info.get('group_id'):
                known[origin] = dict(info)

        live: Dict[str, Dict[str, str]] = {}
        confirmed_platforms = set()
        allowed_platforms = set()
        insts = []
        try:
            manager = getattr(self.context, 'platform_manager', None)
            if manager is not None:
                insts = manager.get_insts() or []
        except Exception as e:
            logger.warning(f"获取平台列表失败，暂不发送联机插件更新通知: {e}")
            return {}

        for platform in insts:
            try:
                meta = platform.meta()
            except Exception as exc:
                logger.debug(f"读取平台元数据失败，跳过该平台: {exc}")
                continue
            platform_name = getattr(meta, 'name', '')
            platform_id = str(getattr(meta, 'id', '') or '')
            if not platform_id or not platform_name or platform_name == 'discord':
                continue
            allowed_platforms.add(platform_id)
            if platform_name != 'aiocqhttp':
                continue
            bot = getattr(platform, 'bot', None)
            if bot is None or not hasattr(bot, 'call_action'):
                continue
            try:
                group_list = await asyncio.wait_for(
                    bot.call_action(action='get_group_list'), timeout=15
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"获取群列表失败（平台 {platform_id}），将使用已记录的群: {e}")
                continue
            if not isinstance(group_list, list):
                logger.warning(f"群列表接口返回格式异常（平台 {platform_id}），将使用已记录的群")
                continue
            confirmed_platforms.add(platform_id)
            for item in group_list:
                if not isinstance(item, dict):
                    continue
                group_id = item.get('group_id') or item.get('groupId')
                if group_id is None:
                    continue
                group_id = str(group_id)
                origin = f"{platform_id}:GroupMessage:{group_id}"
                live[origin] = {
                    'platform_id': platform_id,
                    'group_id': group_id,
                    'name': str(item.get('group_name') or item.get('groupName') or ''),
                }

        # 按发送时实际使用的会话前缀过滤，兼容修复前保存的 Discord 频道。
        groups = {}
        for origin, info in known.items():
            platform_id = origin.split(':', 1)[0]
            if platform_id in allowed_platforms and platform_id not in confirmed_platforms:
                groups[origin] = info
        groups.update(live)
        self._tmp_update_groups = dict(groups)
        return groups

    def _is_tmp_update_group_excluded(
        self,
        origin: str,
        info: Dict[str, str],
        excludes: set,
    ) -> bool:
        if not excludes:
            return False
        group_id = str(info.get('group_id') or '')
        platform_id = str(info.get('platform_id') or '')
        candidates = {origin, group_id}
        if platform_id and group_id:
            candidates.add(f"{platform_id}:GroupMessage:{group_id}")
            candidates.add(f"{platform_id}:{group_id}")
        if platform_id:
            candidates.add(f"{platform_id}:*")
        candidates.add('*')
        return bool(candidates & excludes)

    async def _fetch_tmp_plugin_version(self) -> Optional[Dict[str, Any]]:
        if not self.session:
            return None
        timeout = self._cfg_int('api_timeout_seconds', 10)
        try:
            async with self.session.get(self.TMP_VERSION_API, timeout=timeout) as resp:
                if resp.status != 200:
                    logger.warning(f"检测联机插件版本失败: 错误代码 HTTP {resp.status}")
                    return None
                data = await read_json(resp, limit=1024 * 1024)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"检测联机插件版本请求异常: {e}")
            return None

        if not isinstance(data, dict):
            logger.warning("检测联机插件版本失败: 接口返回格式异常")
            return None
        name = data.get('name') or data.get('version')
        if not name:
            logger.warning(f"检测联机插件版本失败: 缺少版本号，返回内容 {str(data)[:200]}")
            return None
        return {
            'name': str(name),
            'ets2': str(data.get('supported_game_version') or '未知'),
            'ats': str(data.get('supported_ats_game_version') or '未知'),
            'numeric': str(data.get('numeric') or ''),
            'stage': str(data.get('stage') or ''),
            'api_time': str(data.get('time') or ''),
        }

    async def _fetch_tmp_official_game_version(self) -> Dict[str, str]:
        """获取 Steam 官方欧卡版本

        数据来自插件内置/自定义 API 源的 /other/tmpVersion 接口；
        该值只用于通知展示和兼容性提示，不参与 TMP 更新判断。
        接口不可用时版本留空，通知里显示为「未知」。
        """
        if not self.session:
            return {'ets2': ''}
        timeout = self._cfg_int('api_timeout_seconds', 10)
        for base in self._api_bases():
            url = f"{base}/other/tmpVersion"
            try:
                async with self.session.get(url, timeout=timeout) as resp:
                    if resp.status != 200:
                        continue
                    payload = await read_json(resp, limit=1024 * 1024)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug(f"获取 TMP 版本失败，尝试下一个 API 源: {exc}")
                continue
            if not isinstance(payload, dict):
                continue
            code = payload.get('code')
            if code not in (None, 200, '200'):
                continue
            data = payload.get('data')
            official_ets2 = None
            if isinstance(data, dict):
                official_ets2 = (
                    data.get('officialGameVersion')
                    or data.get('officialEts2GameVersion')
                    or data.get('officialETS2GameVersion')
                    or data.get('officialEts2Version')
                )
            official_ets2 = official_ets2 or payload.get('officialGameVersion')
            if official_ets2:
                return {'ets2': str(official_ets2)}
        logger.warning("获取官方 Steam 游戏版本失败，通知中显示为未知")
        return {'ets2': ''}

    def _start_tmp_update_task(self) -> None:
        if not self._tmp_update_enabled():
            logger.info("联机插件自动更新检测已关闭")
            return
        if self._tmp_update_task and not self._tmp_update_task.done():
            return
        self._tmp_update_task = asyncio.create_task(self._tmp_update_loop())
        logger.info(
            "联机插件自动更新检测已启动，"
            f"检测间隔 {self._tmp_update_interval_seconds() // 60} 分钟"
        )

    async def _tmp_update_loop(self) -> None:
        try:
            await asyncio.sleep(min(30, self._tmp_update_interval_seconds()))
            while True:
                try:
                    await self._check_tmp_plugin_update()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"联机插件自动更新检测异常: {e}", exc_info=True)
                await asyncio.sleep(self._tmp_update_interval_seconds())
        except asyncio.CancelledError:
            logger.info("联机插件自动更新检测任务已停止")
            raise

    async def _check_tmp_plugin_update(self) -> None:
        async with self._tmp_update_check_lock:
            await self._check_tmp_plugin_update_locked()

    async def _check_tmp_plugin_update_locked(self) -> None:
        snapshot = await self._fetch_tmp_plugin_version()
        if not snapshot:
            return

        prev = self._tmp_update_state.get('last_snapshot')
        prev_key = self._tmp_version_key(prev)
        new_key = self._tmp_version_key(snapshot)
        now_ts = time.time()

        pending = self._tmp_update_state.get('pending')
        if not isinstance(pending, dict) or not isinstance(pending.get('snapshot'), dict):
            pending = None

        if not any(prev_key):
            logger.info(
                "已记录联机插件版本基线: "
                f"{new_key[0]}（欧卡 {new_key[1]} / 美卡 {new_key[2]}）"
            )
            pending = (
                {'snapshot': snapshot, 'notified': [], 'attempts': 0}
                if self._tmp_update_notify_first_run()
                else None
            )
            self._tmp_update_state['last_snapshot'] = snapshot
            self._tmp_update_state['last_check_ts'] = now_ts
            self._tmp_update_state['pending'] = pending
            self._save_tmp_update_state()
            if pending:
                await self._broadcast_pending_tmp_update(pending)
            return

        if new_key != prev_key:
            logger.info(
                "检测到联机插件更新: "
                f"{prev_key[0]} -> {new_key[0]}"
                f"（欧卡 {prev_key[1]} -> {new_key[1]}，"
                f"美卡 {prev_key[2]} -> {new_key[2]}）"
            )
            pending = {'snapshot': snapshot, 'notified': [], 'attempts': 0}
            self._tmp_update_state['last_snapshot'] = snapshot
        else:
            logger.info(
                "联机插件版本无变化: "
                f"{new_key[0]}（欧卡 {new_key[1]} / 美卡 {new_key[2]}）"
            )

        self._tmp_update_state['last_check_ts'] = now_ts
        self._tmp_update_state['pending'] = pending
        self._save_tmp_update_state()

        if pending:
            await self._broadcast_pending_tmp_update(pending)

    async def _broadcast_pending_tmp_update(self, pending: Dict[str, Any]) -> None:
        snapshot = pending.get('snapshot') or {}
        notified = pending.get('notified')
        if not isinstance(notified, list):
            notified = []
        notified_set = {
            self._tmp_update_group_key(str(origin), self._tmp_update_groups.get(str(origin), {}))
            for origin in notified if origin
        }
        pending['notified'] = sorted(notified_set)

        if not hasattr(self.context, 'send_message'):
            logger.warning("当前 AstrBot 版本不允许主动发送消息，无法推送联机插件更新通知")
            return

        all_groups = await self._discover_tmp_update_groups()
        excludes = self._parse_tmp_update_excludes()

        groups_by_key: Dict[str, Tuple[str, Dict[str, str]]] = {}
        excluded_keys = set()
        for origin, info in all_groups.items():
            group_key = self._tmp_update_group_key(origin, info)
            groups_by_key.setdefault(group_key, (origin, info))
            if self._is_tmp_update_group_excluded(origin, info, excludes):
                excluded_keys.add(group_key)

        targets: List[Tuple[str, Dict[str, str]]] = []
        excluded_count = len(excluded_keys)
        skipped_count = 0
        for group_key, (origin, info) in groups_by_key.items():
            if group_key in excluded_keys:
                continue
            if group_key in notified_set:
                skipped_count += 1
                continue
            targets.append((origin, info))

        if not targets:
            if not all_groups:
                logger.warning("未发现可用群聊，联机插件更新通知将在下次检测时重试")
                return
            logger.info(
                "联机插件更新通知无需发送："
                f"已发送 {skipped_count} 个群，已排除 {excluded_count} 个群"
            )
            self._tmp_update_state['pending'] = None
            self._save_tmp_update_state()
            return

        # 官方 Steam 版本只在真正推送时查询，避免每次检测都多请求一次
        official = snapshot.get('official')
        if not isinstance(official, dict) or not official.get('ets2'):
            official_versions = await self._fetch_tmp_official_game_version()
            if official_versions.get('ets2'):
                snapshot['official'] = official_versions
                pending['snapshot'] = snapshot
                self._save_tmp_update_state()

        message = self._format_tmp_update_message(snapshot)
        delay = self._tmp_update_send_delay()
        sent = 0
        failed: List[str] = []

        logger.info(
            "开始推送联机插件更新通知："
            f"目标 {len(targets)} 个群，已排除 {excluded_count} 个群，"
            f"版本 {snapshot.get('name') or '未知'}"
        )

        for index, (origin, info) in enumerate(targets):
            label = info.get('name') or info.get('group_id') or origin
            try:
                ok = await asyncio.wait_for(
                    self.context.send_message(
                        origin,
                        MessageEventResult().message(message),
                    ),
                    timeout=30,
                )
                if ok is False:
                    raise RuntimeError("未找到匹配的平台适配器")
                notified_set.add(self._tmp_update_group_key(origin, info))
                pending['notified'] = sorted(notified_set)
                self._save_tmp_update_state()
                sent += 1
                logger.info(f"已推送联机插件更新通知到群 {label}（{origin}）")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                failed.append(origin)
                logger.error(f"推送联机插件更新通知到群 {label}（{origin}）失败: {e}")

            if delay > 0 and index < len(targets) - 1:
                await asyncio.sleep(delay)

        self._tmp_update_state['last_notify_ts'] = time.time()
        if failed:
            pending['attempts'] = int(pending.get('attempts') or 0) + 1
            attempts = pending['attempts']
            if attempts >= self.TMP_UPDATE_MAX_NOTIFY_ATTEMPTS:
                logger.error(
                    "联机插件更新通知连续发送失败 "
                    f"{attempts} 次，放弃剩余 {len(failed)} 个群："
                    + ", ".join(failed[:10])
                )
                self._tmp_update_state['pending'] = None
            else:
                self._tmp_update_state['pending'] = pending
                logger.warning(
                    "联机插件更新通知本轮发送完成："
                    f"成功 {sent} 个，失败 {len(failed)} 个，"
                    "失败的群将在下次检测时重试"
                )
        else:
            self._tmp_update_state['pending'] = None
            logger.info(f"联机插件更新通知已推送到 {sent} 个群")
        self._save_tmp_update_state()

    async def tmpversion(self, event: AstrMessageEvent):
        """[命令: 插件版本] 实时查询 TMP 联机插件版本信息。"""
        if not self.session:
            yield event.plain_result("插件初始化中，请稍后重试")
            return

        try:
            url = "https://api.truckersmp.com/v2/version"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await read_json(response)
                    plugin_ver = data.get("name") or data.get("version") or "未知"
                    ets2_ver = data.get("supported_game_version") or data.get("supported_ets2_version") or "未知"
                    ats_ver = data.get("supported_ats_game_version") or data.get("supported_ats_version") or "未知"
                    official = await self._fetch_tmp_official_game_version()
                    official_ets2 = str(official.get('ets2') or '').strip()
                    official_display = official_ets2 or '未知'
                    if official_ets2:
                        ets2_compatible = '✅' if ets2_ver != '未知' and official_ets2 == str(ets2_ver) else '❌'
                        official_major_minor = self._tmp_major_minor(official_ets2)
                        ats_major_minor = self._tmp_major_minor(str(ats_ver))
                        ats_compatible = (
                            '✅'
                            if ats_ver != '未知' and official_major_minor and official_major_minor == ats_major_minor
                            else '❌'
                        )
                    else:
                        ets2_compatible = '未知'
                        ats_compatible = '未知'

                    message = (
                        f"联机插件版本: {plugin_ver}\n"
                        f"支持欧卡版本: {ets2_ver}\n"
                        f"支持美卡版本: {ats_ver}\n"
                        "-----------------------------\n"
                        f"📊 官方Steam版本: {official_display}\n"
                        f"🎮 欧卡兼容: {ets2_compatible}\n"
                        f"🎮 美卡兼容: {ats_compatible}"
                    )
                    yield event.plain_result(message)
                else:
                    yield event.plain_result(f"查询版本信息失败，API返回错误状态码: {response.status}")
        except Exception:
            yield event.plain_result("查询版本信息失败，请稍后重试。")
