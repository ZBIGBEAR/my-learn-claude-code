# My Learn Claude Code

一个用于学习和实践 Claude Code 的项目。

## 项目结构

```
.
├── c1_agent_loop.py     # Agent Loop - 代理循环
├── c2_tool_use.py       # Tool Use - 工具使用
├── c3_todo_write.py     # Todo Write - 待办事项写入
├── c4_sub_agent.py      # Sub Agent - 子代理
├── c5_skill_loading.py  # Skill Loading - 技能加载
├── c6_context_compact.py # Context Compact - 上下文压缩
├── c7_permission.py     # Permission - 权限管理
├── c8_hook_system.py    # Hook System - 钩子系统
├── util/                # 工具函数
├── llm/                 # LLM 相关资料
├── cpu-paper/           # CPU 论文资料
├── .env                 # 环境变量配置
└── requirements.txt     # Python 依赖
```

## 课程内容

本项目包含 8 个 Claude Code 核心概念的学习笔记和代码示例：

1. **Agent Loop** - 理解 Claude Code 的代理循环机制
2. **Tool Use** - 掌握工具的使用方法
3. **Todo Write** - 待办事项的写入和管理
4. **Sub Agent** - 子代理的实现和应用
5. **Skill Loading** - 技能的加载机制
6. **Context Compact** - 上下文压缩优化
7. **Permission** - 权限管理系统
8. **Hook System** - 钩子系统的使用

## 环境配置

1. 创建虚拟环境（已存在 `.venv`）
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 使用说明

```bash
# 激活虚拟环境
source .venv/bin/activate

# 运行示例
python test.py

# 或运行具体课程文件
python c1_agent_loop.py
```