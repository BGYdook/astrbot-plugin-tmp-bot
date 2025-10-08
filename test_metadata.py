#!/usr/bin/env python3
"""
测试AstrBot插件metadata.yaml完整性
"""

import yaml
import sys

def test_metadata_completeness():
    """测试metadata.yaml的完整性"""
    try:
        with open('metadata.yaml', 'r', encoding='utf-8') as f:
            metadata = yaml.safe_load(f)
        
        print("🔍 检查metadata.yaml完整性...")
        print("=" * 60)
        
        # 基本字段检查
        basic_fields = {
            'name': '插件名称',
            'description': '插件描述', 
            'version': '版本号',
            'main': '主文件',
            'author': '作者',
            'homepage': '主页',
            'repo': '仓库地址',
            'license': '许可证'
        }
        
        print("📋 基本信息字段:")
        for field, desc in basic_fields.items():
            if field in metadata:
                print(f"✓ {desc} ({field}): {metadata[field]}")
            else:
                print(f"✗ 缺少 {desc} ({field})")
                return False
        
        print("\n🎯 功能特性:")
        if 'features' in metadata and isinstance(metadata['features'], list):
            for i, feature in enumerate(metadata['features'], 1):
                print(f"✓ {i}. {feature}")
        else:
            print("✗ 缺少功能特性列表")
            return False
        
        print(f"\n📝 支持的命令 ({len(metadata.get('commands', []))} 个):")
        if 'commands' in metadata and isinstance(metadata['commands'], list):
            for cmd in metadata['commands']:
                if isinstance(cmd, dict) and 'name' in cmd and 'description' in cmd:
                    print(f"✓ {cmd['name']}: {cmd['description']}")
                    if 'usage' in cmd:
                        print(f"   用法: {cmd['usage']}")
                else:
                    print(f"✗ 命令格式错误: {cmd}")
                    return False
        else:
            print("✗ 缺少命令列表")
            return False
        
        print(f"\n🏷️  关键词 ({len(metadata.get('keywords', []))} 个):")
        if 'keywords' in metadata and isinstance(metadata['keywords'], list):
            print(f"✓ {', '.join(metadata['keywords'])}")
        else:
            print("✗ 缺少关键词")
            return False
        
        print(f"\n📦 依赖项 ({len(metadata.get('dependencies', []))} 个):")
        if 'dependencies' in metadata and isinstance(metadata['dependencies'], list):
            for dep in metadata['dependencies']:
                print(f"✓ {dep}")
        else:
            print("✗ 缺少依赖项")
            return False
        
        print(f"\n🐍 Python版本要求:")
        if 'python_requires' in metadata:
            print(f"✓ {metadata['python_requires']}")
        else:
            print("✗ 缺少Python版本要求")
            return False
        
        # 检查额外字段
        extra_fields = ['usage', 'data_source', 'api_docs']
        print(f"\n📖 额外信息:")
        for field in extra_fields:
            if field in metadata:
                if field == 'usage':
                    lines = str(metadata[field]).strip().split('\n')
                    print(f"✓ 使用说明 ({len(lines)} 行)")
                else:
                    print(f"✓ {field}: {metadata[field]}")
            else:
                print(f"⚠️  可选字段 {field} 未设置")
        
        return True
        
    except Exception as e:
        print(f"✗ metadata.yaml 测试失败: {e}")
        return False

def test_yaml_syntax():
    """测试YAML语法正确性"""
    try:
        with open('metadata.yaml', 'r', encoding='utf-8') as f:
            yaml.safe_load(f)
        print("✓ YAML语法正确")
        return True
    except yaml.YAMLError as e:
        print(f"✗ YAML语法错误: {e}")
        return False
    except Exception as e:
        print(f"✗ 文件读取失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始测试AstrBot插件metadata.yaml...")
    print("=" * 60)
    
    # 测试YAML语法
    print("1. 测试YAML语法:")
    syntax_success = test_yaml_syntax()
    print()
    
    # 测试完整性
    print("2. 测试内容完整性:")
    completeness_success = test_metadata_completeness()
    print()
    
    # 总结
    print("=" * 60)
    if syntax_success and completeness_success:
        print("🎉 所有测试通过！metadata.yaml已完善")
        print("📢 插件信息现在可以在AstrBot插件市场正确展示")
        return 0
    else:
        print("❌ 部分测试失败，请检查metadata.yaml配置")
        return 1

if __name__ == "__main__":
    sys.exit(main())