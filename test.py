# test_debug.py
import aiohttp
import asyncio

async def test_player_api():
    test_ids = ["1", "123", "5972918"]  # 测试多个ID
    
    for tmp_id in test_ids:
        print(f"\n🔍 测试玩家ID: {tmp_id}")
        
        try:
            url = f"https://api.truckyapp.com/v3/player/{tmp_id}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    print(f"   状态码: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        print(f"   完整响应: {data}")
                        
                        if data.get('response'):
                            player = data['response']
                            print(f"   ✅ 找到玩家: {player.get('name')}")
                        else:
                            print("   ❌ 响应中没有response字段")
                    else:
                        error_text = await response.text()
                        print(f"   ❌ 错误: {error_text}")
                        
        except Exception as e:
            print(f"   💥 异常: {e}")

if __name__ == "__main__":
    asyncio.run(test_player_api())