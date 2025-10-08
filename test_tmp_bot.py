#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
pytest测试文件 - 使用真实的TmpBotPlugin类进行测试
"""

import pytest
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from main import TmpBotPlugin, PlayerNotFoundException, NetworkException, ApiResponseException


class TestTmpBotPlugin:
    """TmpBotPlugin测试类"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录用于测试"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_context(self, temp_dir):
        """创建模拟的Context对象"""
        context = Mock()
        context.get_data_dir.return_value = Path(temp_dir)
        return context
    
    @pytest.fixture
    def plugin(self, mock_context):
        """创建TmpBotPlugin实例"""
        return TmpBotPlugin(mock_context)
    
    def test_initial_bindings_empty(self, plugin):
        """测试初始绑定状态为空"""
        bindings = plugin._load_bindings()
        assert bindings == {}
    
    def test_bind_tmp_id(self, plugin):
        """测试绑定TMP ID"""
        user_id = "test_user_123"
        tmp_id = "654321"
        
        # 绑定
        result = plugin._bind_tmp_id(user_id, tmp_id)
        assert result is True
        
        # 验证绑定
        bound_id = plugin._get_bound_tmp_id(user_id)
        assert bound_id == tmp_id
    
    def test_unbind_tmp_id(self, plugin):
        """测试解绑TMP ID"""
        user_id = "test_user_456"
        tmp_id = "789012"
        
        # 先绑定
        plugin._bind_tmp_id(user_id, tmp_id)
        assert plugin._get_bound_tmp_id(user_id) == tmp_id
        
        # 解绑
        result = plugin._unbind_tmp_id(user_id)
        assert result is True
        
        # 验证解绑
        bound_id = plugin._get_bound_tmp_id(user_id)
        assert bound_id is None
    
    def test_multiple_users_binding(self, plugin):
        """测试多用户绑定"""
        users = [
            ("user1", "111111"),
            ("user2", "222222"),
            ("user3", "333333")
        ]
        
        # 绑定多个用户
        for user_id, tmp_id in users:
            plugin._bind_tmp_id(user_id, tmp_id)
        
        # 验证所有绑定
        for user_id, tmp_id in users:
            assert plugin._get_bound_tmp_id(user_id) == tmp_id
    
    def test_overwrite_binding(self, plugin):
        """测试覆盖现有绑定"""
        user_id = "test_user_overwrite"
        old_tmp_id = "111111"
        new_tmp_id = "999999"
        
        # 初始绑定
        plugin._bind_tmp_id(user_id, old_tmp_id)
        assert plugin._get_bound_tmp_id(user_id) == old_tmp_id
        
        # 覆盖绑定
        plugin._bind_tmp_id(user_id, new_tmp_id)
        assert plugin._get_bound_tmp_id(user_id) == new_tmp_id
    
    def test_persistence_across_instances(self, mock_context, temp_dir):
        """测试跨实例持久化"""
        user_id = "persistent_user"
        tmp_id = "persistent_id"
        
        # 第一个实例
        plugin1 = TmpBotPlugin(mock_context)
        plugin1._bind_tmp_id(user_id, tmp_id)
        
        # 第二个实例
        plugin2 = TmpBotPlugin(mock_context)
        bound_id = plugin2._get_bound_tmp_id(user_id)
        assert bound_id == tmp_id
    
    def test_json_file_format(self, plugin):
        """测试JSON文件格式"""
        user_id = "format_test_user"
        tmp_id = "format_test_id"
        
        plugin._bind_tmp_id(user_id, tmp_id)
        
        # 直接读取JSON文件验证格式
        with open(plugin.binding_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert isinstance(data, dict)
        assert user_id in data
        assert data[user_id] == tmp_id
    
    @pytest.mark.asyncio
    async def test_query_player_info_success(self, plugin):
        """测试查询玩家信息成功"""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "name": "TestPlayer",
            "joinDate": "2023-01-01",
            "vtc": {"name": "TestVTC"}
        })
        
        with patch.object(plugin, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_get_session.return_value = mock_session
            
            result = await plugin._query_player_info("123456")
            
            assert result["name"] == "TestPlayer"
            assert result["joinDate"] == "2023-01-01"
    
    @pytest.mark.asyncio
    async def test_query_player_info_not_found(self, plugin):
        """测试查询不存在的玩家"""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"error": True})
        
        with patch.object(plugin, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_get_session.return_value = mock_session
            
            with pytest.raises(PlayerNotFoundException):
                await plugin._query_player_info("999999")
    
    @pytest.mark.asyncio
    async def test_query_player_info_api_error(self, plugin):
        """测试API错误响应"""
        mock_response = Mock()
        mock_response.status = 500
        
        with patch.object(plugin, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_get_session.return_value = mock_session
            
            with pytest.raises(ApiResponseException):
                await plugin._query_player_info("123456")
    
    def test_extract_tmp_id_valid(self, plugin):
        """测试提取有效的TMP ID"""
        test_cases = [
            ("tmpquery 123456", "tmpquery", "123456"),
            ("tmpquery123456", "tmpquery", "123456"),
            ("tmpposition 789012", "tmpposition", "789012"),
            ("tmpposition789012", "tmpposition", "789012"),
        ]
        
        for message, command, expected in test_cases:
            result = plugin._extract_tmp_id(message, command)
            assert result == expected
    
    def test_extract_tmp_id_invalid(self, plugin):
        """测试提取无效的TMP ID"""
        test_cases = [
            ("tmpquery", "tmpquery"),
            ("tmpquery abc", "tmpquery"),
            ("tmpposition", "tmpposition"),
            ("invalid command", "tmpquery"),
        ]
        
        for message, command in test_cases:
            result = plugin._extract_tmp_id(message, command)
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])