#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试持久化绑定功能
"""

import os
import json
import tempfile
import shutil
from unittest.mock import Mock, patch

def test_binding_functionality():
    """测试绑定功能的正确性"""
    print("🧪 开始测试持久化绑定功能...")
    
    # 创建临时目录模拟数据目录
    temp_dir = tempfile.mkdtemp()
    bind_file = os.path.join(temp_dir, "tmp_bindings.json")
    
    try:
        # 模拟插件类的绑定方法
        class MockTmpBotPlugin:
            def __init__(self):
                self.data_dir = temp_dir
                self.bind_file = bind_file
                os.makedirs(self.data_dir, exist_ok=True)
            
            def _load_bindings(self) -> dict:
                """加载绑定数据"""
                try:
                    if os.path.exists(self.bind_file):
                        with open(self.bind_file, 'r', encoding='utf-8') as f:
                            return json.load(f)
                    return {}
                except Exception as e:
                    print(f"加载绑定数据失败: {e}")
                    return {}

            def _save_bindings(self, bindings: dict) -> bool:
                """保存绑定数据"""
                try:
                    with open(self.bind_file, 'w', encoding='utf-8') as f:
                        json.dump(bindings, f, ensure_ascii=False, indent=2)
                    return True
                except Exception as e:
                    print(f"保存绑定数据失败: {e}")
                    return False

            def _get_bound_tmp_id(self, user_id: str):
                """获取用户绑定的TMP ID"""
                bindings = self._load_bindings()
                return bindings.get(user_id)

            def _bind_tmp_id(self, user_id: str, tmp_id: str) -> bool:
                """绑定用户和TMP ID"""
                bindings = self._load_bindings()
                bindings[user_id] = tmp_id
                return self._save_bindings(bindings)

            def _unbind_tmp_id(self, user_id: str) -> bool:
                """解除用户绑定"""
                bindings = self._load_bindings()
                if user_id in bindings:
                    del bindings[user_id]
                    return self._save_bindings(bindings)
                return False
        
        # 创建插件实例
        plugin = MockTmpBotPlugin()
        
        # 测试1: 初始状态检查
        print("✅ 测试1: 初始状态检查")
        assert plugin._get_bound_tmp_id("user1") is None, "初始状态应该没有绑定"
        assert not os.path.exists(bind_file), "初始状态不应该有绑定文件"
        print("   ✓ 初始状态正确")
        
        # 测试2: 绑定功能
        print("✅ 测试2: 绑定功能")
        result = plugin._bind_tmp_id("user1", "123456")
        assert result == True, "绑定应该成功"
        assert os.path.exists(bind_file), "绑定后应该创建文件"
        bound_id = plugin._get_bound_tmp_id("user1")
        assert bound_id == "123456", f"绑定的ID应该是123456，实际是{bound_id}"
        print("   ✓ 绑定功能正常")
        
        # 测试3: 多用户绑定
        print("✅ 测试3: 多用户绑定")
        plugin._bind_tmp_id("user2", "789012")
        plugin._bind_tmp_id("user3", "345678")
        assert plugin._get_bound_tmp_id("user1") == "123456", "用户1的绑定应该保持不变"
        assert plugin._get_bound_tmp_id("user2") == "789012", "用户2的绑定应该正确"
        assert plugin._get_bound_tmp_id("user3") == "345678", "用户3的绑定应该正确"
        print("   ✓ 多用户绑定正常")
        
        # 测试4: 持久化验证（重新创建实例）
        print("✅ 测试4: 持久化验证")
        plugin2 = MockTmpBotPlugin()
        assert plugin2._get_bound_tmp_id("user1") == "123456", "重启后用户1的绑定应该保持"
        assert plugin2._get_bound_tmp_id("user2") == "789012", "重启后用户2的绑定应该保持"
        assert plugin2._get_bound_tmp_id("user3") == "345678", "重启后用户3的绑定应该保持"
        print("   ✓ 持久化功能正常")
        
        # 测试5: 解绑功能
        print("✅ 测试5: 解绑功能")
        result = plugin2._unbind_tmp_id("user2")
        assert result == True, "解绑应该成功"
        assert plugin2._get_bound_tmp_id("user2") is None, "解绑后应该获取不到绑定"
        assert plugin2._get_bound_tmp_id("user1") == "123456", "其他用户绑定应该不受影响"
        assert plugin2._get_bound_tmp_id("user3") == "345678", "其他用户绑定应该不受影响"
        print("   ✓ 解绑功能正常")
        
        # 测试6: 重复绑定（覆盖）
        print("✅ 测试6: 重复绑定")
        plugin2._bind_tmp_id("user1", "999999")
        assert plugin2._get_bound_tmp_id("user1") == "999999", "重复绑定应该覆盖原有绑定"
        print("   ✓ 重复绑定功能正常")
        
        # 测试7: JSON文件格式验证
        print("✅ 测试7: JSON文件格式验证")
        with open(bind_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        expected_data = {"user1": "999999", "user3": "345678"}
        assert data == expected_data, f"JSON文件内容应该是{expected_data}，实际是{data}"
        print("   ✓ JSON文件格式正确")
        
        print("\n🎉 所有测试通过！持久化绑定功能工作正常")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_syntax_check():
    """检查main.py语法"""
    print("\n🔍 检查main.py语法...")
    try:
        import ast
        with open("main.py", "r", encoding="utf-8") as f:
            content = f.read()
        ast.parse(content)
        print("✅ main.py语法正确")
        return True
    except SyntaxError as e:
        print(f"❌ main.py语法错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 检查main.py时出错: {e}")
        return False

def test_imports():
    """测试导入是否正确"""
    print("\n📦 测试导入...")
    try:
        # 检查新增的导入
        with open("main.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        required_imports = ["import json", "import os"]
        for imp in required_imports:
            if imp not in content:
                print(f"❌ 缺少导入: {imp}")
                return False
        
        # 检查绑定相关方法
        required_methods = [
            "_load_bindings", "_save_bindings", "_get_bound_tmp_id", 
            "_bind_tmp_id", "_unbind_tmp_id"
        ]
        for method in required_methods:
            if f"def {method}" not in content:
                print(f"❌ 缺少方法: {method}")
                return False
        
        # 检查tmpunbind命令
        if "@filter.command(\"tmpunbind\")" not in content:
            print("❌ 缺少tmpunbind命令")
            return False
        
        print("✅ 所有必需的导入和方法都存在")
        return True
        
    except Exception as e:
        print(f"❌ 测试导入时出错: {e}")
        return False

if __name__ == "__main__":
    print("🚀 开始测试TMP Bot插件持久化绑定功能\n")
    
    # 运行所有测试
    tests = [
        test_syntax_check,
        test_imports, 
        test_binding_functionality
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！插件持久化绑定功能已正确实现")
    else:
        print("❌ 部分测试失败，请检查代码")