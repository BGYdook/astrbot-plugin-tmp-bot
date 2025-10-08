@on_command("tmp状态", "检查TMP API状态")
async def tmp_status(self, event: Event, message: Message) -> None:
    """检查TMP API服务状态"""
    try:
        # 测试API连通性
        test_url = "https://api.truckersmp.com/v2/version"
        async with aiohttp.ClientSession() as session:
            async with session.get(test_url, timeout=5) as response:
                if response.status == 200:
                    await event.reply("✅ TMP API 服务正常")
                else:
                    await event.reply(f"❌ TMP API 服务异常 (状态码: {response.status})")
    except Exception as e:
        await event.reply(f"❌ TMP API 无法访问: {str(e)}")