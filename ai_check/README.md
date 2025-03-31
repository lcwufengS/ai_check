# AI协同文件审查系统

## 项目简介

恒AI协同文件审查系统是一个多AI模型协同工作的文件审查平台，通过组织者（Organizer）和专家（Expert）角色分工，完成对用户上传文件的分析、讨论与总结，最终输出材料修改建议。系统支持多厂家大模型API调用，流程分阶段可视化，并兼容Word/PDF文件格式。

## 功能特点

- **多模型协同**：支持配置多个AI模型作为专家，各司其职
- **分阶段审查**：分析、讨论、总结三阶段流程，逐步深入
- **多格式支持**：支持Word(.docx)和PDF文件解析
- **实时进度反馈**：展示各阶段进度和专家响应情况
- **过程可视化**：实时显示API调用过程和系统日志
- **结构化报告**：生成包含问题总览、详细修改建议的HTML报告

## 安装指南

### 环境要求

- Python 3.8+
- 相关依赖包（见requirements.txt）

### 安装步骤

1. 克隆或下载本项目
2. 安装依赖包：

```bash
pip install -r requirements.txt
```

3. 配置API密钥：
   - 编辑`config.json`文件，填入您的API密钥和模型配置
   - 配置文件包含组织者和专家的API设置，详见配置说明部分

## 使用方法

1. 启动服务：

```bash
python app.py
```

服务启动后会在8002端口运行。

2. 访问API接口：
   - 上传文件：POST `/upload`
   - 分析文档：POST `/analyze/{review_id}`
   - 讨论文档：POST `/discuss/{review_id}`
   - 总结文档：POST `/summarize/{review_id}`
   - 查看进度：GET `/progress/{review_id}`
   - 获取报告：GET `/report/{review_id}`

3. 查看报告：
   - 报告生成后会保存在reports目录下
   - 可通过`/report/{review_id}`接口获取HTML格式的报告
   - 报告包含完整的审查过程和修改建议

## API文档

启动服务后，访问 http://localhost:8002/docs 查看完整的API文档。

## 配置说明

`config.json` 文件包含以下配置：

- **organizer**：组织者模型配置
  - api_base：API基础URL
  - model_name：模型名称
  - api_key：API密钥
  - role_name：角色名称（固定为"organizer"）

- **experts**：专家模型配置列表
  - api_base：API基础URL
  - model_name：模型名称
  - api_key：API密钥
  - role_name：角色名称（固定为"expert"）
  - expertise：专业领域描述

## 注意事项

- API密钥请妥善保管，不要泄露
- 文件大小限制为10MB
- 仅支持.docx和.pdf格式文件