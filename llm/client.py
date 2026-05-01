"""Doubao LLM Client (Volcengine)"""
import anthropic
from dotenv import load_dotenv
import os

load_dotenv(override=True)
SYSTEM = (
    f"你叫哆啦A梦，位于 {os.getcwd()}，你是一个编码智能体。"
    "使用 bash 命令检查和修改工作空间。先执行操作，再清晰汇报结果。"
)

TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read file contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace exact text in a file once.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "todo",
        "description": "Rewrite the current session plan for multi-step work.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                            },
                            "activeForm": {
                                "type": "string",
                                "description": "Optional present-continuous label.",
                            },
                        },
                        "required": ["content", "status"],
                    },
                },
            },
            "required": ["items"],
        },
    },
    {
        "name": "compact",
        "description": "Summarize earlier conversation so work can continue in a smaller context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "focus": {"type": "string"},
            },
        },
    },
]

_client = None

MODEL = "MiniMax-M2.7"

def get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL")
        )
    return _client

def chat(messages: list, **kwargs):
    client = get_client()
    max_tokens = kwargs.get("max_tokens", 1024)

    system = kwargs.get("system", SYSTEM)
    tools = kwargs.get("tools", TOOLS)
        # 
    response = client.messages.create(
        model=MODEL,
        system=system,
        messages=messages,
        tools=tools,
        max_tokens=max_tokens
    )
    return response