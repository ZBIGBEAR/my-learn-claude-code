

# 我的 Claude Code 底层原理学习笔记

一个用于学习和实践 Claude Code 底层原理的项目。基于 [shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) 改造，专注于通过大量调试日志看懂 AI agent 的内部运行机制。

## 与原项目的区别

本项目是**学习版**，额外添加了：
- **详细的执行日志**：每次 AI 调用、工具调用、返回值都打印出来，方便追踪 AI 的思考和决策过程
- **调用计数**：精确记录每轮对话调用了多少次 AI 模型
- **内部状态可见**：history 数组、tool results、stop_reason 等关键状态都直接打印

如需看更精简的生产版本，请访问 [my-learn-claude-code-mini](https://github.com/ZBIGBEAR/my-learn-claude-code-mini)。

## 学习资源

| 仓库 | 说明 |
|------|------|
| [shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) | 原项目，19 个章节目录，完整文档 |
| [ZBIGBEAR/my-learn-claude-code](https://github.com/ZBIGBEAR/my-learn-claude-code) | 本仓库，学习版，多调试日志 |
| [ZBIGBEAR/my-learn-claude-code-mini](https://github.com/ZBIGBEAR/my-learn-claude-code-mini) | 精简版，少调试日志，更接近生产 |

## 项目结构

```
my-learn-claude-code/
├── c1_agent_loop.py      # Agent Loop — 代理循环核心
├── c2_tool_use.py        # Tool Use — 工具注册与分发
├── c3_todo_write.py      # Todo Write — 待办事项写入
├── c4_sub_agent.py        # Sub Agent — 子代理与上下文隔离
├── c5_skill_loading.py   # Skill Loading — 技能按需加载
├── c6_context_compact.py  # Context Compact — 上下文压缩
├── c7_permission.py      # Permission — 权限管理管道
├── c8_hook.py            # Hook System — 钩子扩展机制
├── c9_memory.py          # Memory — 跨会话持久记忆
├── c10_system_prompt.py  # System Prompt — 提示词组装
├── c11_error_recovery.py # Error Recovery — 错误恢复与续行
├── c12_task.py           # Task System — 持久化任务系统
├── c13_background_tasks.py # Background Tasks — 后台任务
├── c14_cron_scheduler.py # Cron Scheduler — 定时触发
├── c15_agent_teams.py   # Agent Teams — 多 agent 协作
├── c16_team_protocols.py # Team Protocols — 团队通信协议
├── c17_autonomous_agents.py # Autonomous Agents — 自治认领
├── c18_worktree_task_isolation.py # Worktree — 并行工作目录隔离
├── c19_mcp.py            # MCP & Plugin — 外部工具接入
├── llm/
│   └── client.py         # LLM 客户端（火山引擎 Doubao，兼容 Anthropic API）
├── util/                 # 各模块的核心实现
│   ├── util.py           # execute_tool_calls / extract_text / cron_matches
│   ├── task.py           # 任务管理器
│   ├── memory.py         # 记忆系统
│   ├── hook_manager.py   # 钩子管理
│   ├── permission.py    # 权限检查
│   ├── message_bus.py    # 消息总线
│   ├── teammate_manager.py # 队友管理
│   ├── worktree_manager.py # worktree 管理
│   ├── mcp.py            # MCP 插件加载与路由
│   ├── background_tasks.py # 后台任务
│   ├── cron_scheduler.py # 定时调度
│   └── ...
├── .env                  # 环境变量
```

## 快速开始

```bash
# 配置环境变量（复制 .env.example 为 .env，填入 ANTHROPIC_API_KEY 等）
cp .env.example .env

# 运行最简单的示例（Agent Loop）
python c1_agent_loop.py

# 运行完整版（含 Teams / Worktree / MCP）
python c19_mcp.py
```

### 常用调试命令（在 c19_mcp.py 的 REPL 中）

```
/team    # 查看当前活跃的队友
/inbox   # 查看 lead 的收件箱
/tasks   # 查看任务板
/tools   # 查看当前工具池（含 MCP 工具）
/mcp     # 查看已连接的 MCP 服务器
q        # 退出
```

## 19 个核心概念对照表

| 文件 | 概念 | 关键机制 |
|------|------|----------|
| `c1_agent_loop.py` | Agent Loop | history 数组 + stop_reason 判断 + 循环调用 chat() |
| `c2_tool_use.py` | Tool Use | 工具注册 / 分发 / tool_result 组装 |
| `c3_todo_write.py` | Todo Write | 计划系统，把大目标拆成步骤 |
| `c4_sub_agent.py` | Sub Agent | 上下文隔离，子 history 独立 |
| `c5_skill_loading.py` | Skill Loading | 按需加载技能文件到 prompt |
| `c6_context_compact.py` | Context Compact | 上下文超预算时压缩历史 |
| `c7_permission.py` | Permission | 危险操作前的权限管道 |
| `c8_hook.py` | Hook System | 不改主循环也能注入行为 |
| `c9_memory.py` | Memory | 跨会话持久化记忆 |
| `c10_system_prompt.py` | System Prompt | 提示词组装流水线 |
| `c11_error_recovery.py` | Error Recovery | 出错后状态恢复 |
| `c12_task.py` | Task System | 持久化任务图，而非会话内清单 |
| `c13_background_tasks.py` | Background Tasks | 慢任务后台执行，结果回调 |
| `c14_cron_scheduler.py` | Cron Scheduler | 定时触发任务 |
| `c15_agent_teams.py` | Agent Teams | 多 agent 协作框架 |
| `c16_team_protocols.py` | Team Protocols | 团队通信协议（request/response） |
| `c17_autonomous_agents.py` | Autonomous Agents | 队友自治认领任务 |
| `c18_worktree_task_isolation.py` | Worktree Isolation | git worktree 并行隔离 |
| `c19_mcp.py` | MCP & Plugin | 外部工具平台接入 |

## 关键日志示例

学习版的核心价值在于日志。以下是 `c1_agent_loop.py` 运行时的典型输出：

```
======对话轮次：1======

======对话轮次：1，当前轮对话调用ai次数：1======
======ai回复：[text block], stop_reason：tool_use======
======ai回复：[tool_use block], stop_reason：tool_use======

======对话轮次：1，当前轮对话调用ai次数：2======
======ai回复：[tool_use block], stop_reason：tool_use======

======对话轮次：1，当前轮对话调用ai次数：3======
======ai回复：[text block], stop_reason：stopped======

======第1轮对话最终回复===============
（最终文本输出）
```

通过这些日志，你可以清楚看到：
1. **AI 思考了几轮**：stop_reason == "tool_use" 时说明 AI 还想继续
2. **每次调用返回了什么**：text 还是 tool_use
3. **工具调用的参数和结果**：execute_tool_calls 打印完整输入输出
4. **什么时候结束**：stop_reason == "stopped"

## LLM 配置

默认使用**火山引擎 Doubao**（MiniMax-M2.7），兼容 Anthropic SDK：

```python
# llm/client.py
MODEL = "MiniMax-M2.7"
client = anthropic.Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    base_url=os.getenv("ANTHROPIC_BASE_URL")  # 火山引擎地址
)
```

如需切换为 Claude，需修改 `llm/client.py` 中的 `MODEL` 变量（例如改为 `claude-3-5-sonnet-20241022`），并配置对应的 `ANTHROPIC_API_KEY` 和 `ANTHROPIC_BASE_URL` 即可。

## 环境变量

```bash
# .env
ANTHROPIC_API_KEY=your_api_key
ANTHROPIC_BASE_URL=https://ark.cn-beijing.volces.com/api/v3  # Doubao 地址
```

## 技术栈

- **模型**：MiniMax-M2.7（通过火山引擎 Ark API，Anthropic 兼容）
- **语言**：Python 3.12+
- **工具**：Anthropic Python SDK, python-dotenv
- **应用**：React + Vite（前端），Node.js + Express + SQLite（后端）
