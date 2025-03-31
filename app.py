# -*- coding: utf-8 -*-
import os
import logging
import asyncio
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any, List, Optional
import tempfile
import shutil
import json
from pathlib import Path

from modules.config_manager import ConfigManager
from modules.role_manager import RoleManager
from modules.file_parser import FileParser
from modules.review_process import ReviewProcess

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)

logger = logging.getLogger(__name__)

# 创建自定义日志处理器，用于收集日志信息
class LogCollector(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logs = []
    
    def emit(self, record):
        log_entry = {
            "time": self.formatter.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage()
        }
        self.logs.append(log_entry)
    
    def get_logs(self):
        return self.logs
    
    def clear(self):
        self.logs = []

# 创建日志收集器实例
log_collector = LogCollector()
log_collector.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(log_collector)

# 创建临时目录
TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

# 创建上传目录
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 创建报告目录
REPORT_DIR = "reports"
os.makedirs(REPORT_DIR, exist_ok=True)

# 全局变量
config_manager = None
role_manager = None
file_parser = None
review_process = None
active_review = None

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理器"""
    global config_manager, role_manager, file_parser
    
    try:
        # 初始化配置管理器
        config_path = "config.json"
        config_manager = ConfigManager(config_path)
        logger.info("配置管理器初始化成功")
        
        # 初始化角色管理器
        role_manager = RoleManager(config_manager)
        logger.info("角色管理器初始化成功")
        
        # 初始化文件解析器
        file_parser = FileParser(TEMP_DIR)
        logger.info("文件解析器初始化成功")
        
        yield
    except Exception as e:
        logger.error(f"应用初始化失败: {str(e)}")
        raise
    finally:
        if file_parser:
            file_parser.cleanup()
            logger.info("临时文件已清理")

# 创建FastAPI应用
app = FastAPI(
    title="恒AI协同文件审查系统",
    description="多AI模型协同工作的文件审查系统",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
app.mount("/reports", StaticFiles(directory=REPORT_DIR), name="reports")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    """根路径处理函数，返回前端页面"""
    from fastapi.responses import FileResponse
    return FileResponse("static/index.html")

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件处理函数"""
    global file_parser, role_manager, review_process, active_review, log_collector
    
    # 检查文件格式
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in [".docx", ".pdf"]:
        raise HTTPException(status_code=400, detail="不支持的文件格式，仅支持.docx和.pdf格式")
    
    # 检查文件大小
    file_size = 0
    chunk_size = 1024 * 1024  # 1MB
    
    # 创建临时文件
    temp_file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(temp_file_path, "wb") as buffer:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > 10 * 1024 * 1024:  # 10MB
                raise HTTPException(status_code=400, detail="文件大小超过限制（10MB）")
            buffer.write(chunk)
    
    try:
        # 清空日志收集器
        log_collector.clear()
        
        # 创建审查流程实例
        review_process = ReviewProcess(role_manager, file_parser)
        active_review = {
            "file_name": file.filename,
            "file_path": temp_file_path,
            "status": "已上传",
            "review_id": str(hash(file.filename + str(os.path.getmtime(temp_file_path))))
        }
        
        return {
            "message": "文件上传成功",
            "file_name": file.filename,
            "file_size": file_size,
            "review_id": active_review["review_id"]
        }
    except Exception as e:
        logger.error(f"文件上传处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")

@app.post("/analyze/{review_id}")
async def analyze_document(review_id: str, background_tasks: BackgroundTasks):
    """分析文档处理函数"""
    global review_process, active_review
    
    if not review_process or not active_review or active_review["review_id"] != review_id:
        raise HTTPException(status_code=404, detail="未找到有效的审查任务")
    
    try:
        # 在后台任务中执行分析
        background_tasks.add_task(start_analysis, active_review["file_path"])
        
        return {
            "message": "文档分析已开始",
            "review_id": review_id
        }
    except Exception as e:
        logger.error(f"文档分析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文档分析失败: {str(e)}")

async def start_analysis(file_path: str):
    """开始文档分析"""
    global review_process, active_review
    
    try:
        # 执行分析阶段
        analysis_results = await review_process.analyze_document(file_path)
        active_review["status"] = "分析完成"
        active_review["analysis_results"] = analysis_results
        logger.info(f"文档分析完成: {file_path}")
    except Exception as e:
        active_review["status"] = f"分析失败: {str(e)}"
        logger.error(f"文档分析失败: {str(e)}")

@app.post("/discuss/{review_id}")
async def discuss_document(review_id: str, background_tasks: BackgroundTasks):
    """讨论文档处理函数"""
    global review_process, active_review
    
    if not review_process or not active_review or active_review["review_id"] != review_id:
        raise HTTPException(status_code=404, detail="未找到有效的审查任务")
    
    if active_review["status"] != "分析完成":
        raise HTTPException(status_code=400, detail="请先完成文档分析阶段")
    
    try:
        # 在后台任务中执行讨论
        background_tasks.add_task(start_discussion)
        
        return {
            "message": "文档讨论已开始",
            "review_id": review_id
        }
    except Exception as e:
        logger.error(f"文档讨论失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文档讨论失败: {str(e)}")

async def start_discussion():
    """开始文档讨论"""
    global review_process, active_review
    
    try:
        # 执行讨论阶段
        discussion_results = await review_process.discuss_document()
        active_review["status"] = "讨论完成"
        active_review["discussion_results"] = discussion_results
        logger.info("文档讨论完成")
    except Exception as e:
        active_review["status"] = f"讨论失败: {str(e)}"
        logger.error(f"文档讨论失败: {str(e)}")

@app.post("/summarize/{review_id}")
async def summarize_document(review_id: str, background_tasks: BackgroundTasks):
    """总结文档处理函数"""
    global review_process, active_review
    
    if not review_process or not active_review or active_review["review_id"] != review_id:
        raise HTTPException(status_code=404, detail="未找到有效的审查任务")
    
    if active_review["status"] != "讨论完成":
        raise HTTPException(status_code=400, detail="请先完成文档讨论阶段")
    
    try:
        # 在后台任务中执行总结
        background_tasks.add_task(start_summary, review_id)
        
        return {
            "message": "文档总结已开始",
            "review_id": review_id
        }
    except Exception as e:
        logger.error(f"文档总结失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文档总结失败: {str(e)}")

async def start_summary(review_id: str):
    """开始文档总结"""
    global review_process, active_review
    
    try:
        # 执行总结阶段
        final_report = await review_process.generate_summary()
        active_review["status"] = "总结完成"
        active_review["final_report"] = final_report
        
        # 生成HTML报告
        report_path = generate_html_report(review_id, final_report)
        active_review["report_path"] = report_path
        
        logger.info("文档总结完成")
    except Exception as e:
        active_review["status"] = f"总结失败: {str(e)}"
        logger.error(f"文档总结失败: {str(e)}")

def generate_html_report(review_id: str, final_report: Dict[str, Any]) -> str:
    """生成HTML格式报告
    
    Args:
        review_id: 审查ID
        final_report: 最终报告字典
        
    Returns:
        报告文件路径
    """
    # 确保使用绝对值的review_id，避免负号导致的URL问题
    abs_review_id = abs(int(review_id))
    report_file = f"{abs_review_id}.html"
    report_path = os.path.join(os.path.abspath(REPORT_DIR), report_file)
    # 确保reports目录存在
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    # 处理raw_report字段（如果存在）
    if 'raw_report' in final_report:
        try:
            # 尝试解析JSON字符串
            import json
            import re
            # 提取JSON部分（去除可能的markdown代码块标记）
            raw_text = final_report['raw_report']
            json_match = re.search(r'```json\n(.+?)```', raw_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = raw_text
            
            # 解析JSON
            report_data = json.loads(json_str)
            # 更新final_report
            final_report.update(report_data)
        except Exception as e:
            logger.error(f"解析raw_report失败: {str(e)}")
            # 如果解析失败，保留原始文本
            final_report['raw_content'] = final_report['raw_report']
    
    # 构建HTML内容
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>文档审查报告</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            h1, h2, h3 {{ color: #333; }}
            .summary {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
            .priority {{ background-color: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin-bottom: 10px; }}
            .detail {{ margin-bottom: 30px; }}
            .problem {{ border-bottom: 1px solid #eee; padding-bottom: 10px; margin-bottom: 10px; }}
            .problem-type {{ font-weight: bold; color: #555; }}
            .problem-location {{ color: #777; font-style: italic; }}
            .expert-name {{ color: #0066cc; font-weight: bold; }}
            .raw-content {{ white-space: pre-wrap; background-color: #f8f9fa; padding: 15px; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>文档审查报告</h1>
            
            <div class="summary">
                <h2>问题总览</h2>
                <p>{final_report.get('summary', '无问题总览信息')}</p>
            </div>
            
            <h2>高优先级问题</h2>
            <div class="priority-issues">
                {generate_priority_issues_html(final_report.get('priority_issues', []))}
            </div>
            
            <h2>详细修改建议</h2>
            <div class="details">
                {generate_details_html(final_report.get('details', {}))}
            </div>
            
            {generate_raw_report_html(final_report)}
        </div>
    </body>
    </html>
    """
    
    # 写入HTML文件
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return report_path

def generate_priority_issues_html(priority_issues: List) -> str:
    """生成高优先级问题HTML内容
    
    Args:
        priority_issues: 高优先级问题列表
        
    Returns:
        HTML内容
    """
    if not priority_issues:
        return "<p>无高优先级问题</p>"
    
    html = ""
    for issue in priority_issues:
        # 适配不同的字段名称
        problem_type = issue.get('type', issue.get('问题类型', ''))
        problem_location = issue.get('location', issue.get('位置', '未知位置'))
        problem_desc = issue.get('description', issue.get('问题描述', ''))
        problem_suggestion = issue.get('suggestion', issue.get('修改建议', ''))
        problem_expert = issue.get('expert', issue.get('专家来源', ''))
        problem_priority = issue.get('priority', issue.get('优先级', '高'))
        problem_reason = issue.get('reason', issue.get('依据', ''))
        
        # 处理专家来源可能是列表的情况
        if isinstance(problem_expert, list):
            problem_expert = ", ".join(problem_expert)
        
        html += f"""
        <div class="priority">
            <div class="problem-type">{problem_type if problem_type else '优先级: ' + problem_priority}</div>
            <div class="problem-location">{problem_location}</div>
            <p>{problem_desc}</p>
            {f'<p><strong>修改建议:</strong> {problem_suggestion}</p>' if problem_suggestion else ''}
            {f'<p><strong>依据:</strong> {problem_reason}</p>' if problem_reason else ''}
            {f'<p class="expert-name">提出专家: {problem_expert}</p>' if problem_expert else ''}
        </div>
        """
    
    return html

def generate_summary_html(final_report: Dict) -> str:
    """生成问题总览HTML内容
    
    Args:
        final_report: 最终报告字典
        
    Returns:
        HTML内容
    """
    # 处理summary字段
    if isinstance(final_report.get('summary'), dict):
        # 如果summary是字典类型，生成列表形式展示
        html = "<ul>"
        for category, count in final_report['summary'].items():
            html += f"<li><strong>{category}:</strong> {count}</li>"
        html += "</ul>"
        return html
    elif isinstance(final_report.get('summary'), str):
        # 如果summary是字符串，直接显示
        return f"<p>{final_report['summary']}</p>"
    else:
        return "<p>无问题总览信息</p>"

def generate_raw_report_html(final_report: Dict) -> str:
    """生成原始报告HTML内容
    
    Args:
        final_report: 最终报告字典
        
    Returns:
        HTML内容
    """
    if 'raw_content' in final_report:
        return f"""
        <h2>原始报告内容</h2>
        <div class="raw-content">
            {final_report['raw_content']}
        </div>
        """
    return ""

def generate_details_html(details: Dict) -> str:
    """生成详细修改建议HTML内容
    
    Args:
        details: 详细修改建议字典
        
    Returns:
        HTML内容
    """
    if not details:
        return "<p>无详细修改建议</p>"
    
    html = ""
    for section, problems in details.items():
        html += f"<div class=\"detail\">\n<h3>{section}</h3>\n"
        
        if not problems:
            html += "<p>本节无问题</p>\n"
        else:
            for problem in problems:
                # 适配不同的字段名称
                problem_type = problem.get('type', problem.get('问题类型', '未知类型'))
                problem_location = problem.get('location', problem.get('问题位置', '未知位置'))
                problem_desc = problem.get('description', problem.get('问题描述', ''))
                problem_suggestion = problem.get('suggestion', problem.get('修改建议', ''))
                problem_expert = problem.get('expert', problem.get('专家来源', '未知专家'))
                
                # 处理专家来源可能是列表的情况
                if isinstance(problem_expert, list):
                    problem_expert = ", ".join(problem_expert)
                
                html += f"""
                <div class="problem">
                    <div class="problem-type">{problem_type}</div>
                    <div class="problem-location">{problem_location}</div>
                    <p>{problem_desc}</p>
                    <p><strong>修改建议:</strong> {problem_suggestion}</p>
                    <p class="expert-name">提出专家: {problem_expert}</p>
                </div>
                """
        
        html += "</div>\n"
    
    return html

@app.get("/progress/{review_id}")
async def get_progress(review_id: str):
    """获取审查进度处理函数"""
    global review_process, active_review, log_collector
    
    if not review_process or not active_review or active_review["review_id"] != review_id:
        raise HTTPException(status_code=404, detail="未找到有效的审查任务")
    
    # 构建响应数据，包含API响应信息
    response_data = {
        "review_id": review_id,
        "file_name": active_review["file_name"],
        "status": active_review["status"],
        "progress": review_process.get_progress(),
        "logs": log_collector.get_logs()  # 添加日志信息
    }
    
    # 添加API响应信息（如果存在）
    if "api_responses" in active_review:
        response_data["api_responses"] = active_review["api_responses"]
    
    return response_data

@app.get("/report/{review_id}")
async def get_report(review_id: str):
    """获取审查报告处理函数"""
    global active_review
    
    if not active_review or active_review["review_id"] != review_id:
        raise HTTPException(status_code=404, detail="未找到有效的审查任务")
    
    if active_review["status"] != "总结完成":
        raise HTTPException(status_code=400, detail="审查报告尚未生成完成")
    
    # 确保reports目录存在
    os.makedirs(REPORT_DIR, exist_ok=True)
    
    # 确保report_url使用绝对值的review_id，避免负号导致的URL问题
    # 检查是否存在report_path
    if "report_path" in active_review:
        # 从report_path中提取文件名
        report_filename = os.path.basename(active_review["report_path"])
        report_url = f"/reports/{report_filename}"
        
        # 检查报告文件是否存在
        report_file_path = os.path.join(REPORT_DIR, report_filename)
        if not os.path.exists(report_file_path):
            raise HTTPException(status_code=404, detail="报告文件不存在")
    else:
        # 兼容旧逻辑，使用绝对值的review_id
        abs_review_id = abs(int(review_id))
        report_filename = f"{abs_review_id}.html"
        report_url = f"/reports/{report_filename}"
        
        # 检查报告文件是否存在
        report_file_path = os.path.join(REPORT_DIR, report_filename)
        if not os.path.exists(report_file_path):
            raise HTTPException(status_code=404, detail="报告文件不存在")
    
    return {
        "review_id": review_id,
        "report_url": report_url,
        "final_report": active_review["final_report"]
    }

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8002, reload=True)