from llm.client import chat
from util.util import execute_tool_calls
from util.util import extract_text
from pathlib import Path
from util.util import TOOL_HANDLERS
WORKDIR = Path.cwd()
SUBAGENT_SYSTEM = f"You are a coding subagent at {WORKDIR}. Complete the given task, then summarize your findings."
# TOOL_HANDLERS = {
#     "bash":       lambda **kw: run_bash(kw["command"]),
#     "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
#     "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
#     "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
# }

# Child gets all base tools except task (no recursive spawning)
CHILD_TOOLS = [
    {"name": "bash", "description": "Run a shell command.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
]

def run_subagent(prompt: str) -> str:
    print(f"\n======子代理任务：{prompt}======\n")
    sub_messages = [{"role": "user", "content": prompt}]  # fresh context
    for _ in range(30):  # safety limit
        response = chat(sub_messages,system=SUBAGENT_SYSTEM,tools=CHILD_TOOLS)
        sub_messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            break
        results = []
        print(f"\n======子任务：ai回复：{response.content}，stop_reason：{response.stop_reason}======\n")
        for block in response.content:
            if block.type == "tool_use":
                handler = TOOL_HANDLERS.get(block.name)
                output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)[:50000]})
        sub_messages.append({"role": "user", "content": results})
    # Only the final text returns to the parent -- child context is discarded
    return "".join(b.text for b in response.content if hasattr(b, "text")) or "(no summary)"

PARENT_TOOLS = CHILD_TOOLS + [
    {"name": "task", "description": "Spawn a subagent with fresh context. It shares the filesystem but not conversation history.",
     "input_schema": {"type": "object", "properties": {"prompt": {"type": "string"}, "description": {"type": "string", "description": "Short description of the task"}}, "required": ["prompt"]}},
]

# 处理用户的一次对话
def agent_loop(history: list, count: int, sub_count: int):  
    # 打印对话次数
    print(f"\n======对话轮次：{count}======\n")
    while True:
        # 打印对话次数和当前调用ai次数
        print(f"\n======对话轮次：{count}，当前轮对话调用ai次数：{sub_count}======\n")
        
        response = chat(history,tools=PARENT_TOOLS)
        # 提取ai回复的文本内容
        print(f"\n======ai回复：{response.content}，stop_reason：{response.stop_reason}======\n")
        history.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            # 不是工具调用，直接返回
            break

        # 执行工具调用
        results = []
        for block in response.content:
            if block.type == "tool_use":
                if block.name == "task":
                    desc = block.input.get("description", "subtask")
                    prompt = block.input.get("prompt", "")
                    print(f"> task ({desc}): {prompt[:80]}")
                    output = run_subagent(prompt)
                else:
                    handler = TOOL_HANDLERS.get(block.name)
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                print(f"工具：{block.name},结果：{output[:200]}")
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
        # 把工具调用的结果添加到历史记录中
        history.append({"role": "user", "content": results})
        # 继续执行下一次对话
        sub_count += 1

if __name__ == "__main__":
    # 这是个二维数组，记录启动之后所有对话
    # 第一维度是对话轮次
    # 第二维度是对话内容。每次对话包含用户和和助手的对话，以及工具调用的结果，ai可能有多个消息，所以是个数组
    # 每个消息格式：{"role": "user/assistant", "content": "xxxx"}
    history = []
    # 对话轮次
    count = 0
    while True:
        count += 1
        try:
            query = input(">> ")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break

        history.append({"role": "user", "content": query})
        # 当前轮对话调用ai次数
        sub_count = 1
        # 处理对话
        agent_loop(history,count,sub_count)

        # 打印最终回复
        final_text = extract_text(history[-1]["content"])
        if final_text:
            print(f"\n======第{count}轮对话最终回复===============\n{final_text}\n")
        print()