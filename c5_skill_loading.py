from llm.client import chat
from util.util import TOOL_HANDLERS, SetTool
from util.skill_loading import SKILL_REGISTRY,SKILL_LOADING_SYSTEM
from util.util import extract_text

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
        "name": "load_skill",
        "description": "Load the full body of a named skill into the current context.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
]

# 处理用户的一次对话
def agent_loop(history: list, count: int, sub_count: int):  
    # 打印对话次数
    print(f"\n======对话轮次：{count}======\n")
    while True:
        # 打印对话次数和当前调用ai次数
        print(f"\n======对话轮次：{count}，当前轮对话调用ai次数：{sub_count}======\n")
        
        response = chat(history, system=SKILL_LOADING_SYSTEM, tools=TOOLS)
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
                handler = TOOL_HANDLERS.get(block.name)
                print(f"\n=======handler: {handler},args: {block.input}======\n")
                output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                print(f"> {block.name}:")
                print(output[:200])
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
    SetTool("load_skill", SKILL_REGISTRY.load_full_text)
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