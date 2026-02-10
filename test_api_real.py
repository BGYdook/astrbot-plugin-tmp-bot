import http.client
import json
import asyncio
import aiohttp

# 模拟实际的API调用测试
async def test_api_real():
    # 模拟配置中的token（这里需要填入实际的token）
    token = "9770872CD4C4484B942DD82BC2AFFF65"  # 实际使用时需要填入真实token
    
    if not token:
        print("请先提供API token进行测试")
        return
    
    base_url = "https://open.vtcm.link"
    
    # 测试不同的查询参数
    test_params = [
        {"uid": "21770"},
        {"tmpId": "5974821"}, 
        {"qq": "123456"}
    ]
    
    async with aiohttp.ClientSession() as session:
        for params in test_params:
            try:
                print(f"\n{'='*60}")
                print(f"测试参数: {params}")
                print('='*60)
                
                url = f"{base_url}/members/get"
                headers = {"token": token}
                
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        print("返回数据:")
                        print(json.dumps(data, ensure_ascii=False, indent=2))
                        
                        # 分析可能的字段名
                        if isinstance(data, dict) and not data.get("error"):
                            print("\n🔍 字段分析:")
                            for key, value in data.items():
                                if isinstance(value, (str, int, float)):
                                    print(f"  📄 {key}: {value}")
                                elif isinstance(value, dict):
                                    print(f"  📁 {key}: (对象)")
                                    for sub_key, sub_value in value.items():
                                        print(f"    └─ {sub_key}: {sub_value}")
                                elif isinstance(value, list):
                                    print(f"  📋 {key}: (数组，长度: {len(value)})")
                                else:
                                    print(f"  ❓ {key}: {type(value)}")
                            
                            # 专门查找玩家名称和车队角色相关字段
                            print("\n🎯 玩家名称相关字段:")
                            name_fields = ["name", "playerName", "player_name", "username", "userName", 
                                         "nick", "nickname", "displayName", "display_name", "nickName"]
                            for field in name_fields:
                                if field in data:
                                    print(f"  ✅ {field}: {data[field]}")
                            
                            # 检查嵌套对象
                            user_data = data.get("user") or data.get("player") or {}
                            if isinstance(user_data, dict):
                                print("\n🎯 user/player对象中的名称字段:")
                                for field in name_fields:
                                    if field in user_data:
                                        print(f"  ✅ user.{field}: {user_data[field]}")
                            
                            print("\n🎯 车队角色相关字段:")
                            role_fields = ["teamRole", "team_role", "role", "position", "rank", "title", "job", "duty"]
                            for field in role_fields:
                                if field in data:
                                    print(f"  ✅ {field}: {data[field]}")
                            
                            # 检查角色嵌套对象
                            role_data = data.get("role") or data.get("position") or {}
                            if isinstance(role_data, dict):
                                print("\n🎯 role/position对象中的角色字段:")
                                for field in ["name", "title", "position"]:
                                    if field in role_data:
                                        print(f"  ✅ role.{field}: {role_data[field]}")
                    else:
                        print(f"HTTP错误: {response.status}")
                        text = await response.text()
                        print(f"响应: {text}")
                        
            except Exception as e:
                print(f"请求错误: {e}")

# 运行测试
if __name__ == "__main__":
    print("🚀 开始API数据结构测试...")
    print("注意：需要提供有效的API token才能进行真实测试")
    asyncio.run(test_api_real())