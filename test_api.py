import http.client
import json

# 测试API连接和返回数据结构
conn = http.client.HTTPSConnection("open.vtcm.link")
payload = ''
headers = {
    'token': '9770872CD4C4484B942DD82BC2AFFF65'  # 这里需要填入实际的token
}

# 测试不同的查询方式
test_cases = [
    '/members/get?uid=21770',
    '/members/get?tmpId=5974821', 
    '/members/get?qq=123456'
]

for endpoint in test_cases:
    try:
        print(f"\n{'='*50}")
        print(f"测试: {endpoint}")
        print('='*50)
        
        conn.request("GET", endpoint, payload, headers)
        res = conn.getresponse()
        data = res.read()
        result = data.decode("utf-8")
        
        # 尝试解析JSON
        try:
            json_data = json.loads(result)
            print("返回数据:")
            print(json.dumps(json_data, ensure_ascii=False, indent=2))
            
            # 检查可能的字段名
            if isinstance(json_data, dict):
                print("\n字段分析:")
                for key, value in json_data.items():
                    if isinstance(value, (str, int, float)):
                        print(f"  {key}: {value}")
                    elif isinstance(value, dict):
                        print(f"  {key}: (对象)")
                        for sub_key, sub_value in value.items():
                            print(f"    {sub_key}: {sub_value}")
                    else:
                        print(f"  {key}: {type(value)}")
                        
        except json.JSONDecodeError:
            print("原始响应:")
            print(result)
            
    except Exception as e:
        print(f"错误: {e}")

print("\n测试完成！")