# -*- coding: utf-8 -*-
import logging
import os
from typing import Dict, Any, List, Optional
from openai import OpenAI
from .config_manager import ConfigManager

class AIModel:
    """AI模型基类，封装API调用逻辑"""
    
    def __init__(self, api_base: str, model_name: str, api_key: str, role_name: str):
        """初始化AI模型
        
        Args:
            api_base: API基础URL
            model_name: 模型名称
            api_key: API密钥
            role_name: 角色名称
        """
        self.api_base = api_base
        self.model_name = model_name
        self.api_key = api_key
        self.role_name = role_name
        self.client = OpenAI(
            base_url=api_base,
            api_key=api_key
        )
    
    def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.7, stream: bool = False) -> Optional[Dict[str, Any]]:
        """调用聊天补全API
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            stream: 是否使用流式响应
            
        Returns:
            API响应结果，失败时返回None
        """
        # 导入全局变量active_review
        import sys
        import inspect
        current_frame = inspect.currentframe()
        caller_frame = inspect.getouterframes(current_frame, 2)
        caller_globals = caller_frame[1][0].f_globals
        active_review = caller_globals.get('active_review')
        
        try:
            if stream:
                # 流式响应模式
                response_stream = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    stream=True
                )
                
                # 存储API响应到active_review
                if active_review is not None:
                    # 初始化api_responses列表
                    if 'api_responses' not in active_review:
                        active_review['api_responses'] = []
                    
                    # 收集流式响应内容
                    collected_chunks = []
                    collected_content = []
                    
                    # 创建一个新的流对象，同时收集响应内容
                    class ResponseCollector:
                        def __init__(self, stream, role_name):
                            self.stream = stream
                            self.role_name = role_name
                        
                        def __iter__(self):
                            return self
                        
                        def __next__(self):
                            chunk = next(self.stream)
                            # 存储chunk到active_review
                            content = chunk.choices[0].delta.content if chunk.choices[0].delta.content else ''
                            chunk_dict = {
                                'chunk': {
                                    'choices': [{
                                        'delta': {
                                            'content': content
                                        }
                                    }]
                                },
                                'model': self.stream.model,
                                'role': self.role_name
                            }
                            # 只有当内容不为空时才添加到响应列表中
                            if content:
                                active_review['api_responses'].append(chunk_dict)
                                # 限制存储的响应数量，避免内存溢出
                                if len(active_review['api_responses']) > 100:
                                    active_review['api_responses'] = active_review['api_responses'][-100:]
                            return chunk
                    
                    # 返回包装后的流对象
                    return ResponseCollector(response_stream, self.role_name)
                
                # 返回原始流对象
                return response_stream
            else:
                # 普通响应模式
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature
                )
                
                # 存储API响应到active_review
                if active_review is not None:
                    # 初始化api_responses列表
                    if 'api_responses' not in active_review:
                        active_review['api_responses'] = []
                    
                    # 存储响应内容
                    response_dict = {
                        'chunk': {
                            'choices': [{
                                'delta': {
                                    'content': response.choices[0].message.content
                                }
                            }]
                        },
                        'model': self.model_name,
                        'role': self.role_name
                    }
                    active_review['api_responses'].append(response_dict)
                    # 限制存储的响应数量，避免内存溢出
                    if len(active_review['api_responses']) > 100:
                        active_review['api_responses'] = active_review['api_responses'][-100:]
                
                # 将响应对象转换为字典格式，保持与原代码兼容
                return {
                    "choices": [
                        {
                            "message": {
                                "content": response.choices[0].message.content
                            }
                        }
                    ]
                }
        except Exception as e:
            logging.error(f"API调用失败: {str(e)}")
            return None


class OrganizerModel(AIModel):
    """组织者模型，负责协调专家模型"""
    
    def __init__(self, api_base: str, model_name: str, api_key: str):
        """初始化组织者模型
        
        Args:
            api_base: API基础URL
            model_name: 模型名称
            api_key: API密钥
        """
        super().__init__(api_base, model_name, api_key, "organizer")
    
    def generate_analysis_prompt(self, file_content: str) -> str:
        """生成分析阶段的提示词
        
        Args:
            file_content: 文件内容
            
        Returns:
            分析阶段提示词
        """
        # 截取文件内容摘要，避免超出token限制
        content_summary = file_content[:3000] + "..." if len(file_content) > 3000 else file_content
        
        prompt = f"你是一名专业审查专家，请从专业角度分析以下材料，列出需审查的关键要点：\n\n{content_summary}"
        return prompt
    
    def generate_discussion_prompt(self, file_content: str, review_points: str) -> str:
        """生成讨论阶段的提示词
        
        Args:
            file_content: 文件内容
            review_points: 审查要点清单
            
        Returns:
            讨论阶段提示词
        """
        prompt = f"请基于以下审查要点，检查材料的错别字、语句逻辑问题，并给出修改建议。\n\n审查要点清单：\n{review_points}\n\n材料内容：\n{file_content}"
        return prompt
    
    def summarize_review_points(self, expert_outputs: List[Dict[str, Any]]) -> str:
        """汇总专家提出的审查要点
        
        Args:
            expert_outputs: 专家输出列表
            
        Returns:
            汇总后的审查要点清单
        """
        # 调用组织者API汇总要点
        messages = [
            {"role": "system", "content": "你是一名组织者，负责汇总多位专家提出的审查要点，去除重复项，并按重要性排序。"}
        ]
        
        # 添加专家输出
        for i, output in enumerate(expert_outputs):
            expert_name = output.get("model_name", f"专家{i+1}")
            expert_content = output.get("content", "")
            messages.append({"role": "user", "content": f"专家{expert_name}的审查要点：\n{expert_content}"})
        
        # 添加汇总指令
        messages.append({"role": "user", "content": "请汇总以上专家提出的审查要点，去除重复项，并按重要性排序，生成《审查要点清单》。"})
        
        # 调用API
        response = self.chat_completion(messages)
        if response and "choices" in response:
            return response["choices"][0]["message"]["content"]
        return "无法汇总审查要点，请检查API连接。"
    
    def generate_final_report(self, discussion_results: List[Dict[str, Any]], file_content: str) -> Dict[str, Any]:
        """生成最终审查报告
        
        Args:
            discussion_results: 讨论阶段结果
            file_content: 文件内容
            
        Returns:
            最终报告字典
        """
        # 调用组织者API生成最终报告
        messages = [
            {"role": "system", "content": "你是一名组织者，负责汇总多位专家的讨论结果，生成最终审查报告。"}
        ]
        
        # 添加专家讨论结果
        for i, result in enumerate(discussion_results):
            expert_name = result.get("model_name", f"专家{i+1}")
            expert_content = result.get("content", "")
            messages.append({"role": "user", "content": f"专家{expert_name}的讨论结果：\n{expert_content}"})
        
        # 添加报告生成指令
        report_instruction = """
        请根据以上专家讨论结果，生成最终审查报告，包含以下内容：
        1. 问题总览：统计各类问题数量（语法、逻辑、事实性错误等）
        2. 详细修改建议：按章节或段落列出问题及对应专家意见
        3. 优先级标注：高优先级问题需突出显示
        
        请按JSON格式输出，包含以下字段：
        - summary: 问题总览
        - details: 详细修改建议（按章节或段落组织）
        - priority_issues: 高优先级问题列表
        """
        messages.append({"role": "user", "content": report_instruction})
        
        # 调用API
        response = self.chat_completion(messages)
        if response and "choices" in response:
            report_text = response["choices"][0]["message"]["content"]
            try:
                # 尝试解析JSON格式报告
                import json
                report_dict = json.loads(report_text)
                return report_dict
            except:
                # 如果解析失败，返回原始文本
                return {"raw_report": report_text}
        
        return {"error": "无法生成最终报告，请检查API连接。"}


class ExpertModel(AIModel):
    """专家模型，负责特定领域的审查"""
    
    def __init__(self, api_base: str, model_name: str, api_key: str, expertise: str):
        """初始化专家模型
        
        Args:
            api_base: API基础URL
            model_name: 模型名称
            api_key: API密钥
            expertise: 专业领域
        """
        super().__init__(api_base, model_name, api_key, "expert")
        self.expertise = expertise
    
    def analyze_document(self, prompt: str) -> Dict[str, Any]:
        """分析文档内容
        
        Args:
            prompt: 分析提示词
            
        Returns:
            分析结果字典
        """
        # 根据专业领域调整系统提示词
        system_prompt = f"你是一名{self.expertise}专家，请从专业角度分析以下材料，列出需审查的关键要点。"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # 调用API
        response = self.chat_completion(messages)
        if response and "choices" in response:
            return {
                "model_name": self.model_name,
                "expertise": self.expertise,
                "content": response["choices"][0]["message"]["content"],
                "response_time": 0
            }
        
        return {
            "model_name": self.model_name,
            "expertise": self.expertise,
            "content": "API调用失败，无法获取分析结果。",
            "response_time": 0
        }
    
    def discuss_document(self, prompt: str) -> Dict[str, Any]:
        """讨论文档问题
        
        Args:
            prompt: 讨论提示词
            
        Returns:
            讨论结果字典
        """
        # 根据专业领域调整系统提示词
        system_prompt = f"""你是一名{self.expertise}专家，请基于审查要点，检查材料的问题，并给出修改建议。
        请按以下格式输出：
        1. 问题类型：[语法/逻辑/事实性错误/其他]
        2. 问题位置：[章节或段落标识]
        3. 问题描述：[具体描述问题]
        4. 修改建议：[具体修改建议]
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # 调用API
        response = self.chat_completion(messages)
        if response and "choices" in response:
            return {
                "model_name": self.model_name,
                "expertise": self.expertise,
                "content": response["choices"][0]["message"]["content"],
                "response_time": 0
            }
        
        return {
            "model_name": self.model_name,
            "expertise": self.expertise,
            "content": "API调用失败，无法获取讨论结果。",
            "response_time": 0
        }


class RoleManager:
    """角色管理类，负责初始化和管理AI角色"""
    
    def __init__(self, config_manager: ConfigManager):
        """初始化角色管理器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self.organizer = None
        self.experts = []
        self._initialize_roles()
    
    def _initialize_roles(self) -> None:
        """初始化组织者和专家角色"""
        # 初始化组织者
        organizer_config = self.config_manager.get_organizer_config()
        try:
            self.organizer = OrganizerModel(
                api_base=organizer_config["api_base"],
                model_name=organizer_config["model_name"],
                api_key=organizer_config["api_key"]
            )
            logging.info(f"组织者初始化成功: {organizer_config['model_name']}")
        except Exception as e:
            logging.error(f"组织者初始化失败: {str(e)}")
            raise ValueError("组织者初始化失败，请检查配置")
        
        # 初始化专家
        experts_config = self.config_manager.get_experts_config()
        for expert_config in experts_config:
            try:
                expert = ExpertModel(
                    api_base=expert_config["api_base"],
                    model_name=expert_config["model_name"],
                    api_key=expert_config["api_key"],
                    expertise=expert_config["expertise"]
                )
                self.experts.append(expert)
                logging.info(f"专家初始化成功: {expert_config['model_name']} ({expert_config['expertise']})")
            except Exception as e:
                logging.error(f"专家初始化失败: {str(e)}")
                # 跳过不可用的专家模型
    
    def get_organizer(self) -> Optional[OrganizerModel]:
        """获取组织者实例
        
        Returns:
            组织者实例，如果初始化失败则返回None
        """
        return self.organizer
    
    def get_experts(self) -> List[ExpertModel]:
        """获取专家实例列表
        
        Returns:
            专家实例列表
        """
        return self.experts
    
    def get_expert_by_name(self, model_name: str) -> Optional[ExpertModel]:
        """根据模型名称获取专家实例
        
        Args:
            model_name: 模型名称
            
        Returns:
            专家实例，如果未找到则返回None
        """
        for expert in self.experts:
            if expert.model_name == model_name:
                return expert
        return None