# -*- coding: utf-8 -*-
import json
from typing import Dict, Any, List
import os

class ConfigManager:
    """配置管理类，负责加载和验证配置文件"""
    
    def __init__(self, config_path: str):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件
        
        Returns:
            配置字典
        """
        try:
            if not os.path.exists(self.config_path):
                raise FileNotFoundError(f"配置文件 {self.config_path} 不存在")
                
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except json.JSONDecodeError:
            raise ValueError(f"配置文件 {self.config_path} 格式错误，请检查JSON格式")
    
    def _validate_config(self) -> None:
        """验证配置文件格式和必要字段"""
        # 验证组织者配置
        if 'organizer' not in self.config:
            raise ValueError("配置文件缺少'organizer'字段")
        
        required_fields = ['api_base', 'model_name', 'api_key', 'role_name']
        for field in required_fields:
            if field not in self.config['organizer']:
                raise ValueError(f"组织者配置缺少'{field}'字段")
        
        # 验证专家配置
        if 'experts' not in self.config or not isinstance(self.config['experts'], list):
            raise ValueError("配置文件缺少'experts'字段或格式错误")
        
        if len(self.config['experts']) == 0:
            raise ValueError("至少需要配置一个专家")
        
        for i, expert in enumerate(self.config['experts']):
            for field in required_fields + ['expertise']:
                if field not in expert:
                    raise ValueError(f"专家{i+1}配置缺少'{field}'字段")
    
    def get_config(self) -> Dict[str, Any]:
        """获取配置信息
        
        Returns:
            配置字典
        """
        return self.config
    
    def get_organizer_config(self) -> Dict[str, Any]:
        """获取组织者配置
        
        Returns:
            组织者配置字典
        """
        return self.config['organizer']
    
    def get_experts_config(self) -> List[Dict[str, Any]]:
        """获取专家配置列表
        
        Returns:
            专家配置列表
        """
        return self.config['experts']
    
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """更新配置并保存到文件
        
        Args:
            new_config: 新的配置字典
        """
        self.config = new_config
        self._validate_config()
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)