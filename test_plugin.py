#!/usr/bin/env python3
"""
测试AstrBot插件语法和结构
"""

import ast
import sys

def test_python_syntax():
    """测试Python语法正确性"""
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        # 解析AST检查语法
        ast.parse(source_code)
        print("✓ main.py 语法正确")
        return True
        
    except SyntaxError as e:
        print(f"✗ main.py 语法错误: {e}")
        return False
    except Exception as e:
        print(f"✗ main.py 测试失败: {e}")
        return False

def test_plugin_structure():
    """测试插件结构"""
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键组件
        checks = [
            ('class TmpBotPlugin', '插件类定义'),
            ('@register', '插件注册装饰器'),
            ('@filter.command', '命令过滤器'),
            ('async def', '异步方法定义'),
            ('AstrMessageEvent', '消息事件类型'),
            ('tmpquery', 'tmpquery命令'),
            ('tmpbind', 'tmpbind命令'),
            ('tmpposition', 'tmpposition命令'),
            ('tmpserver', 'tmpserver命令'),
            ('tmpversion', 'tmpversion命令')
        ]
        
        all_passed = True
        for check, description in checks:
            if check in content:
                print(f"✓ {description} 存在")
            else:
                print(f"✗ {description} 不存在")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"✗ 插件结构测试失败: {e}")
        return False

def test_metadata():
    """测试metadata.yaml配置"""
    try:
        import yaml
        with open('metadata.yaml', 'r', encoding='utf-8') as f:
            metadata = yaml.safe_load(f)
        
        required_fields = ['name', 'description', 'version', 'main', 'author']
        for field in required_fields:
            if field in metadata:
                print(f"✓ metadata.yaml 包含 {field}: {metadata[field]}")
            else:
                print(f"✗ metadata.yaml 缺少 {field}")
                return False
        
        # 检查main字段是否指向main.py
        if metadata.get('main') == 'main.py':
            print("✓ main字段正确指向main.py")
        else:
            print(f"✗ main字段错误: {metadata.get('main')}")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ metadata.yaml 测试失败: {e}")
        return False

def test_requirements():
    """测试requirements.txt"""
    try:
        with open('requirements.txt', 'r', encoding='utf-8') as f:
            requirements = f.read().strip().split('\n')
        
        expected_deps = ['aiohttp', 'httpx', 'pydantic', 'python-dateutil']
        
        for dep in expected_deps:
            found = any(dep in req for req in requirements)
            if found:
                print(f"✓ requirements.txt 包含 {dep}")
            else:
                print(f"✗ requirements.txt 缺少 {dep}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ requirements.txt 测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始测试AstrBot插件转换结果...")
    print("=" * 60)
    
    # 测试Python语法
    print("1. 测试Python语法:")
    syntax_success = test_python_syntax()
    print()
    
    # 测试插件结构
    print("2. 测试插件结构:")
    structure_success = test_plugin_structure()
    print()
    
    # 测试metadata
    print("3. 测试metadata.yaml:")
    metadata_success = test_metadata()
    print()
    
    # 测试requirements
    print("4. 测试requirements.txt:")
    requirements_success = test_requirements()
    print()
    
    # 总结
    print("=" * 60)
    if all([syntax_success, structure_success, metadata_success, requirements_success]):
        print("✓ 所有测试通过！插件转换成功")
        print("插件已成功从Koishi格式转换为AstrBot格式")
        return 0
    else:
        print("✗ 部分测试失败，请检查插件配置")
        return 1

if __name__ == "__main__":
    sys.exit(main())