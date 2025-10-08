import aiohttp
import asyncio

async def test_tmp_api():
    """直接在终端测试TMP API"""
    print("🔍 测试TMP API连接...")
    
    try:
        # 测试主要API
        url = "https://api.truckersmp.com/v2/player/1"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                print(f"📊 API状态码: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ API正常 - 玩家: {data.get('name', '未知')}")
                else:
                    print(f"❌ API异常 - 状态码: {response.status}")
                    
    except Exception as e:
        print(f"💥 连接失败: {e}")

# 运行测试
if __name__ == "__main__":
    asyncio.run(test_tmp_api())