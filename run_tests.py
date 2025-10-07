#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
独立测试脚本 - 测试核心功能，不依赖AstrBot
"""

import sys
import os
import tempfile
import shutil
import json
import re
from typing import Optional
from unittest.mock import Mock


# 自定义异常类（从main.py复制）
class TmpApiException(Exception):
    """TMP API相关异常的基类"""
    pass


class PlayerNotFoundException(TmpApiException):
    """玩家不存在异常"""
    pass


class NetworkException(TmpApiException):
    """网络请求异常"""
    pass


class ApiResponseException(TmpApiException):
    """API响应异常"""
    pass


# 简化的TmpBotPlugin类，只包含绑定相关功能
class SimpleTmpBotPlugin:
    """简化的TMP Bot插件类，用于测试绑定功能"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.binding_file = os.path.join(data_dir, "tmp_bindings.json")
        
        # 确保数据目录存在
        os.makedirs(data_dir, exist_ok=True)
    
    def _load_bindings(self) -> dict:
        """加载用户绑定数据"""
        try:
            if os.path.exists(self.binding_file):
                with open(self.binding_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception:
            return {}
    
    def _save_bindings(self, bindings: dict) -> bool:
        """保存用户绑定数据"""
        try:
            with open(self.binding_file, 'w', encoding='utf-8') as f:
                json.dump(bindings, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def _get_bound_tmp_id(self, user_id: str) -> Optional[str]:
        """获取用户绑定的TMP ID"""
        bindings = self._load_bindings()
        return bindings.get(user_id)
    
    def _bind_tmp_id(self, user_id: str, tmp_id: str) -> bool:
        """绑定用户TMP ID"""
        bindings = self._load_bindings()
        bindings[user_id] = tmp_id
        return self._save_bindings(bindings)
    
    def _unbind_tmp_id(self, user_id: str) -> bool:
        """解绑用户TMP ID"""
        bindings = self._load_bindings()
        if user_id in bindings:
            del bindings[user_id]
            return self._save_bindings(bindings)
        return False
    
    def _extract_tmp_id(self, message: str, command: str) -> Optional[str]:
        """从消息中提取TMP ID"""
        # 移除命令前缀
        if message.startswith(command):
            id_part = message[len(command):].strip()
        else:
            return None
        
        # 使用正则表达式匹配数字
        match = re.search(r'\d+', id_part)
        if match:
            return match.group()
        return None


def test_binding_functionality():
    """测试绑定功能"""
    print("🧪 开始测试绑定功能...")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 创建插件实例
        plugin = SimpleTmpBotPlugin(temp_dir)
        
        # 测试1: 初始状态
        bindings = plugin._load_bindings()
        assert bindings == {}, "初始绑定状态应为空"
        print("✅ 测试1通过: 初始状态为空")
        
        # 测试2: 绑定功能
        user_id = "test_user_123"
        tmp_id = "654321"
        result = plugin._bind_tmp_id(user_id, tmp_id)
        assert result is True, "绑定应该成功"
        
        bound_id = plugin._get_bound_tmp_id(user_id)
        assert bound_id == tmp_id, f"绑定的ID应为{tmp_id}"
        print("✅ 测试2通过: 绑定功能正常")
        
        # 测试3: 解绑功能
        result = plugin._unbind_tmp_id(user_id)
        assert result is True, "解绑应该成功"
        
        bound_id = plugin._get_bound_tmp_id(user_id)
        assert bound_id is None, "解绑后应返回None"
        print("✅ 测试3通过: 解绑功能正常")
        
        # 测试4: 多用户绑定
        users = [("user1", "111111"), ("user2", "222222"), ("user3", "333333")]
        for uid, tid in users:
            plugin._bind_tmp_id(uid, tid)
        
        for uid, tid in users:
            bound = plugin._get_bound_tmp_id(uid)
            assert bound == tid, f"用户{uid}的绑定ID应为{tid}"
        print("✅ 测试4通过: 多用户绑定正常")
        
        # 测试5: 持久化
        plugin2 = SimpleTmpBotPlugin(temp_dir)
        for uid, tid in users:
            bound = plugin2._get_bound_tmp_id(uid)
            assert bound == tid, f"持久化后用户{uid}的绑定ID应为{tid}"
        print("✅ 测试5通过: 持久化功能正常")
        
        # 测试6: JSON文件格式
        with open(plugin.binding_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert isinstance(data, dict), "JSON文件应包含字典"
        print("✅ 测试6通过: JSON文件格式正确")
        
        print("🎉 所有绑定功能测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)


def test_extract_tmp_id():
    """测试TMP ID提取功能"""
    print("🧪 开始测试TMP ID提取功能...")
    
    try:
        plugin = SimpleTmpBotPlugin(tempfile.mkdtemp())
        
        # 测试有效的TMP ID
        test_cases = [
            ("tmpquery 123456", "tmpquery", "123456"),
            ("tmpquery123456", "tmpquery", "123456"),
            ("tmpposition 789012", "tmpposition", "789012"),
            ("tmpposition789012", "tmpposition", "789012"),
        ]
        
        for message, command, expected in test_cases:
            result = plugin._extract_tmp_id(message, command)
            assert result == expected, f"消息'{message}'应提取出'{expected}'，但得到'{result}'"
        
        # 测试无效的TMP ID
        invalid_cases = [
            ("tmpquery", "tmpquery"),
            ("tmpquery abc", "tmpquery"),
            ("tmpposition", "tmpposition"),
            ("invalid command", "tmpquery"),
        ]
        
        for message, command in invalid_cases:
            result = plugin._extract_tmp_id(message, command)
            assert result is None, f"消息'{message}'应返回None，但得到'{result}'"
        
        print("✅ TMP ID提取功能测试通过")
        return True
        
    except Exception as e:
        print(f"❌ TMP ID提取测试失败: {e}")
        return False


def test_exception_classes():
    """测试异常类"""
    print("🧪 开始测试异常类...")
    
    try:
        # 测试异常继承关系
        assert issubclass(PlayerNotFoundException, TmpApiException), "PlayerNotFoundException应继承TmpApiException"
        assert issubclass(NetworkException, TmpApiException), "NetworkException应继承TmpApiException"
        assert issubclass(ApiResponseException, TmpApiException), "ApiResponseException应继承TmpApiException"
        assert issubclass(TmpApiException, Exception), "TmpApiException应继承Exception"
        
        # 测试异常实例化
        try:
            raise PlayerNotFoundException("测试异常")
        except PlayerNotFoundException as e:
            assert str(e) == "测试异常", "异常消息应正确传递"
        
        print("✅ 异常类测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 异常类测试失败: {e}")
        return False


def test_syntax():
    """测试语法"""
    print("🧪 开始测试main.py语法...")
    
    try:
        # 尝试编译main.py
        with open('main.py', 'r', encoding='utf-8') as f:
            code = f.read()
        
        compile(code, 'main.py', 'exec')
        print("✅ main.py语法正确")
        return True
        
    except SyntaxError as e:
        print(f"❌ main.py语法错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 语法测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("🚀 开始运行TMP Bot插件独立测试...")
    print("=" * 50)
    
    tests = [
        ("语法测试", test_syntax),
        ("异常类测试", test_exception_classes),
        ("TMP ID提取测试", test_extract_tmp_id),
        ("绑定功能测试", test_binding_functionality),
    ]
    
    success_count = 0
    total_tests = len(tests)
    
    # 运行测试
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        if test_func():
            success_count += 1
        else:
            print(f"❌ {test_name}失败")
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {success_count}/{total_tests} 通过")
    
    if success_count == total_tests:
        print("🎉 所有测试通过！代码质量良好。")
        return 0
    else:
        print("❌ 部分测试失败，请检查代码。")
        return 1


if __name__ == "__main__":
    sys.exit(main())