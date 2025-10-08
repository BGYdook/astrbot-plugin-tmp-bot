#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
独立测试修复后的API调用功能
"""

import asyncio
import aiohttp
import json

class ApiTester:
    """API测试器"""
    
    def __init__(self):
        self.session = None
    
    async def _get_session(self):
        """获取HTTP会话"""
        if self.session is None:
            # 添加浏览器请求头来尝试绕过Cloudflare保护
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'cross-site'
            }
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session
    
    async def test_player_info(self, tmp_id: str):
        """测试玩家信息查询"""
        session = await self._get_session()
        try:
            # 使用TruckersMP API查询玩家基本信息
            async with session.get(f"https://api.truckersmp.com/v2/player/{tmp_id}") as resp:
                print(f"   状态码: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('error'):
                        print(f"   ❌ API返回错误: {data.get('error')}")
                        return None
                    # TruckersMP API返回格式: {"response": {...}, "error": false}
                    player_data = data.get('response', {})
                    print(f"   ✅ 玩家信息查询成功")
                    print(f"   玩家名: {player_data.get('name', '未知')}")
                    print(f"   玩家ID: {player_data.get('id', '未知')}")
                    print(f"   注册时间: {player_data.get('joinDate', '未知')}")
                    return player_data
                elif resp.status == 404:
                    print(f"   ❌ 玩家 {tmp_id} 不存在")
                    return None
                elif resp.status == 403:
                    print(f"   ❌ API访问被拒绝 (Cloudflare保护)")
                    return None
                else:
                    print(f"   ❌ API返回错误状态码: {resp.status}")
                    return None
        except Exception as e:
            print(f"   ❌ 请求失败: {e}")
            return None
    
    async def test_player_online(self, tmp_id: str):
        """测试玩家在线状态查询"""
        session = await self._get_session()
        try:
            async with session.get(f"https://api.truckyapp.com/v3/map/online?playerID={tmp_id}") as resp:
                print(f"   状态码: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✅ 在线状态查询成功")
                    print(f"   在线状态: {'在线' if data.get('online') else '离线'}")
                    if data.get('server'):
                        print(f"   服务器: {data.get('server')}")
                    return data
                else:
                    print(f"   ❌ 在线状态查询失败，状态码: {resp.status}")
                    return None
        except Exception as e:
            print(f"   ❌ 请求失败: {e}")
            return None
    
    async def test_servers(self):
        """测试服务器状态查询"""
        session = await self._get_session()
        try:
            # 使用TruckersMP API查询服务器状态
            async with session.get("https://api.truckersmp.com/v2/servers") as resp:
                print(f"   状态码: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('error'):
                        print(f"   ❌ API返回错误: {data.get('error')}")
                        return None
                    
                    servers = data.get('response', [])
                    print(f"   ✅ 服务器状态查询成功")
                    print(f"   服务器数量: {len(servers)}")
                    
                    if servers:
                        print("   前3个服务器:")
                        for i, server in enumerate(servers[:3]):
                            name = server.get('name', '未知')
                            players = server.get('players', 0)
                            max_players = server.get('maxplayers', 0)
                            online = server.get('online', False)
                            status = "🟢" if online else "🔴"
                            print(f"     {i+1}. {status} {name} - {players}/{max_players}")
                    
                    return servers
                elif resp.status == 403:
                    print(f"   ❌ API访问被拒绝 (Cloudflare保护)")
                    return None
                else:
                    print(f"   ❌ API返回错误状态码: {resp.status}")
                    return None
        except Exception as e:
            print(f"   ❌ 请求失败: {e}")
            return None
    
    async def close(self):
        """关闭会话"""
        if self.session:
            await self.session.close()

async def test_fixed_api():
    """测试修复后的API功能"""
    print("🚀 测试修复后的API功能...")
    print("=" * 50)
    
    tester = ApiTester()
    
    try:
        # 测试玩家信息查询
        print("📋 测试玩家信息查询 (ID: 1):")
        await tester.test_player_info("1")
        
        print()
        
        # 测试在线状态查询
        print("📋 测试在线状态查询 (ID: 1):")
        await tester.test_player_online("1")
        
        print()
        
        # 测试服务器状态查询
        print("📋 测试服务器状态查询:")
        await tester.test_servers()
        
        print()
        
        # 测试并发请求
        print("📋 测试并发请求处理:")
        try:
            tasks = [
                tester.test_player_online("1"),
                tester.test_player_online("2"),
                tester.test_player_online("3")
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if r is not None and not isinstance(r, Exception))
            print(f"   ✅ 并发请求完成，成功: {success_count}/{len(tasks)}")
        except Exception as e:
            print(f"   ❌ 并发请求失败: {e}")
        
    finally:
        # 清理资源
        await tester.close()
    
    print()
    print("=" * 50)
    print("🎉 API功能测试完成！")

if __name__ == "__main__":
    asyncio.run(test_fixed_api())