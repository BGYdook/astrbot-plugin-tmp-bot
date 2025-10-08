#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
API接口测试脚本
用于测试TruckersMP API端点的可用性和响应格式
"""

import asyncio
import aiohttp
import json
import time

async def test_api_endpoints():
    """测试API端点"""
    print("🚀 开始测试TruckersMP API端点...")
    print("=" * 50)
    
    # 添加请求头，模拟浏览器请求
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        # 测试TruckersMP服务器列表API
        print("📋 测试TruckersMP服务器列表API:")
        try:
            start_time = time.time()
            async with session.get("https://api.truckersmp.com/v2/servers") as resp:
                end_time = time.time()
                print(f"   状态码: {resp.status}")
                print(f"   响应时间: {(end_time - start_time):.2f}秒")
                
                if resp.status == 200:
                    data = await resp.json()
                    if not data.get('error'):
                        servers = data.get('response', [])
                        print(f"   服务器数量: {len(servers)}")
                        if servers:
                            first_server = servers[0]
                            print(f"   示例服务器: {first_server.get('name', '未知')}")
                            print(f"   玩家数: {first_server.get('players', 0)}/{first_server.get('maxplayers', 0)}")
                        print("   ✅ TruckersMP服务器列表API正常")
                    else:
                        print(f"   ❌ API返回错误: {data.get('error')}")
                else:
                    response_text = await resp.text()
                    print(f"   ❌ TruckersMP服务器列表API异常，状态码: {resp.status}")
                    print(f"   响应内容: {response_text[:200]}...")
        except Exception as e:
            print(f"   ❌ TruckersMP服务器列表API请求失败: {e}")
        
        print()
        
        # 测试TruckersMP玩家信息API
        print("📋 测试TruckersMP玩家信息API:")
        test_player_id = "1"  # 使用ID 1作为测试
        try:
            start_time = time.time()
            async with session.get(f"https://api.truckersmp.com/v2/player/{test_player_id}") as resp:
                end_time = time.time()
                print(f"   状态码: {resp.status}")
                print(f"   响应时间: {(end_time - start_time):.2f}秒")
                
                if resp.status == 200:
                    data = await resp.json()
                    if not data.get('error'):
                        player_data = data.get('response', {})
                        print(f"   玩家名: {player_data.get('name', '未知')}")
                        print(f"   玩家ID: {player_data.get('id', '未知')}")
                        print("   ✅ TruckersMP玩家信息API正常")
                    else:
                        print(f"   ❌ API返回错误: {data.get('error')}")
                else:
                    response_text = await resp.text()
                    print(f"   ❌ TruckersMP玩家信息API异常，状态码: {resp.status}")
                    print(f"   响应内容: {response_text[:200]}...")
        except Exception as e:
            print(f"   ❌ TruckersMP玩家信息API请求失败: {e}")
        
        print()
        
        # 测试TruckyApp在线状态API（这个仍然可用）
        print("📋 测试TruckyApp在线状态API:")
        try:
            start_time = time.time()
            async with session.get(f"https://api.truckyapp.com/v3/map/online?playerID={test_player_id}") as resp:
                end_time = time.time()
                print(f"   状态码: {resp.status}")
                print(f"   响应时间: {(end_time - start_time):.2f}秒")
                
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   在线状态: {'在线' if data.get('online') else '离线'}")
                    if data.get('server'):
                        print(f"   服务器: {data.get('server')}")
                    print("   ✅ TruckyApp在线状态API正常")
                else:
                    response_text = await resp.text()
                    print(f"   ❌ TruckyApp在线状态API异常，状态码: {resp.status}")
                    print(f"   响应内容: {response_text[:200]}...")
        except Exception as e:
            print(f"   ❌ TruckyApp在线状态API请求失败: {e}")
    
    print()
    print("=" * 50)
    print("🎉 API测试完成！")

if __name__ == "__main__":
    asyncio.run(test_api_endpoints())