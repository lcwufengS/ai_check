# -*- coding: utf-8 -*-
import logging
import asyncio
from typing import Dict, Any, List, Optional
import time
from .role_manager import RoleManager, OrganizerModel, ExpertModel
from .file_parser import FileParser

class ReviewProcess:
    """审查流程类，负责协调分析、讨论和总结三个阶段"""
    
    def __init__(self, role_manager: RoleManager, file_parser: FileParser):
        """初始化审查流程
        
        Args:
            role_manager: 角色管理器实例
            file_parser: 文件解析器实例
        """
        self.role_manager = role_manager
        self.file_parser = file_parser
        self.organizer = role_manager.get_organizer()
        self.experts = role_manager.get_experts()
        self.file_content = ""
        self.review_points = ""
        self.analysis_results = []
        self.discussion_results = []
        self.final_report = {}
        self.progress = {
            "stage": "初始化",
            "status": "准备中",
            "expert_progress": {}
        }
    
    def update_progress(self, stage: str, status: str, expert_name: str = None, expert_status: str = None) -> None:
        """更新进度信息
        
        Args:
            stage: 当前阶段
            status: 当前状态
            expert_name: 专家名称
            expert_status: 专家状态
        """
        self.progress["stage"] = stage
        self.progress["status"] = status
        
        if expert_name and expert_status:
            self.progress["expert_progress"][expert_name] = expert_status
        
        logging.info(f"进度更新: {stage} - {status}")
    
    def get_progress(self) -> Dict[str, Any]:
        """获取当前进度信息
        
        Returns:
            进度信息字典
        """
        return self.progress
    
    async def analyze_document(self, file_path: str) -> Dict[str, Any]:
        """分析阶段：解析文件并收集专家审查要点
        
        Args:
            file_path: 文件路径
            
        Returns:
            分析结果字典
        """
        self.update_progress("分析阶段", "开始解析文件")
        
        try:
            # 解析文件
            file_result = self.file_parser.parse_file(file_path)
            self.file_content = file_result["content"]
            self.update_progress("分析阶段", f"文件解析完成: {file_result['file_name']}")
            
            # 生成分析提示词
            prompt = self.organizer.generate_analysis_prompt(self.file_content)
            
            # 并行调用所有专家进行分析
            self.update_progress("分析阶段", f"开始收集专家审查要点 (0/{len(self.experts)})")
            
            # 创建专家分析任务
            expert_tasks = []
            for expert in self.experts:
                self.progress["expert_progress"][expert.model_name] = "分析中"
                expert_tasks.append(self._analyze_with_expert(expert, prompt))
            
            # 等待所有专家完成分析
            self.analysis_results = await asyncio.gather(*expert_tasks)
            
            # 汇总审查要点
            self.update_progress("分析阶段", "汇总审查要点")
            self.review_points = self.organizer.summarize_review_points(self.analysis_results)
            
            self.update_progress("分析阶段", "完成")
            
            return {
                "file_info": file_result,
                "expert_results": self.analysis_results,
                "review_points": self.review_points
            }
        except Exception as e:
            self.update_progress("分析阶段", f"失败: {str(e)}")
            logging.error(f"分析阶段失败: {str(e)}")
            raise
    
    async def _analyze_with_expert(self, expert: ExpertModel, prompt: str) -> Dict[str, Any]:
        """使用单个专家进行分析
        
        Args:
            expert: 专家模型实例
            prompt: 分析提示词
            
        Returns:
            专家分析结果
        """
        try:
            start_time = time.time()
            result = expert.analyze_document(prompt)
            elapsed_time = time.time() - start_time
            
            # 更新专家进度
            self.progress["expert_progress"][expert.model_name] = "完成"
            completed = sum(1 for status in self.progress["expert_progress"].values() if status == "完成")
            self.update_progress("分析阶段", f"收集专家审查要点 ({completed}/{len(self.experts)})")
            
            # 添加耗时信息
            result["elapsed_time"] = elapsed_time
            return result
        except Exception as e:
            self.progress["expert_progress"][expert.model_name] = f"失败: {str(e)}"
            logging.error(f"专家{expert.model_name}分析失败: {str(e)}")
            return {
                "model_name": expert.model_name,
                "expertise": expert.expertise,
                "content": f"分析失败: {str(e)}",
                "elapsed_time": 0
            }
    
    async def discuss_document(self) -> Dict[str, Any]:
        """讨论阶段：专家基于审查要点讨论文档问题
        
        Returns:
            讨论结果字典
        """
        if not self.file_content or not self.review_points:
            raise ValueError("请先完成分析阶段")
        
        self.update_progress("讨论阶段", "开始讨论文档问题")
        
        try:
            # 生成讨论提示词
            prompt = self.organizer.generate_discussion_prompt(self.file_content, self.review_points)
            
            # 重置专家进度
            for expert in self.experts:
                self.progress["expert_progress"][expert.model_name] = "讨论中"
            
            # 并行调用所有专家进行讨论
            self.update_progress("讨论阶段", f"收集专家讨论结果 (0/{len(self.experts)})")
            
            # 创建专家讨论任务
            expert_tasks = []
            for expert in self.experts:
                expert_tasks.append(self._discuss_with_expert(expert, prompt))
            
            # 等待所有专家完成讨论
            self.discussion_results = await asyncio.gather(*expert_tasks)
            
            self.update_progress("讨论阶段", "完成")
            
            return {
                "expert_results": self.discussion_results
            }
        except Exception as e:
            self.update_progress("讨论阶段", f"失败: {str(e)}")
            logging.error(f"讨论阶段失败: {str(e)}")
            raise
    
    async def _discuss_with_expert(self, expert: ExpertModel, prompt: str) -> Dict[str, Any]:
        """使用单个专家进行讨论
        
        Args:
            expert: 专家模型实例
            prompt: 讨论提示词
            
        Returns:
            专家讨论结果
        """
        try:
            start_time = time.time()
            result = expert.discuss_document(prompt)
            elapsed_time = time.time() - start_time
            
            # 更新专家进度
            self.progress["expert_progress"][expert.model_name] = "完成"
            completed = sum(1 for status in self.progress["expert_progress"].values() if status == "完成")
            self.update_progress("讨论阶段", f"收集专家讨论结果 ({completed}/{len(self.experts)})")
            
            # 添加耗时信息
            result["elapsed_time"] = elapsed_time
            return result
        except Exception as e:
            self.progress["expert_progress"][expert.model_name] = f"失败: {str(e)}"
            logging.error(f"专家{expert.model_name}讨论失败: {str(e)}")
            return {
                "model_name": expert.model_name,
                "expertise": expert.expertise,
                "content": f"讨论失败: {str(e)}",
                "elapsed_time": 0
            }
    
    async def generate_summary(self) -> Dict[str, Any]:
        """总结阶段：生成最终审查报告
        
        Returns:
            最终报告字典
        """
        if not self.discussion_results:
            raise ValueError("请先完成讨论阶段")
        
        self.update_progress("总结阶段", "开始生成最终报告")
        
        try:
            # 生成最终报告
            self.final_report = self.organizer.generate_final_report(self.discussion_results, self.file_content)
            
            self.update_progress("总结阶段", "完成")
            
            return self.final_report
        except Exception as e:
            self.update_progress("总结阶段", f"失败: {str(e)}")
            logging.error(f"总结阶段失败: {str(e)}")
            raise
    
    def get_analysis_results(self) -> List[Dict[str, Any]]:
        """获取分析阶段结果
        
        Returns:
            分析结果列表
        """
        return self.analysis_results
    
    def get_discussion_results(self) -> List[Dict[str, Any]]:
        """获取讨论阶段结果
        
        Returns:
            讨论结果列表
        """
        return self.discussion_results
    
    def get_final_report(self) -> Dict[str, Any]:
        """获取最终报告
        
        Returns:
            最终报告字典
        """
        return self.final_report
    
    def cleanup(self) -> None:
        """清理临时资源"""
        self.file_parser.cleanup()