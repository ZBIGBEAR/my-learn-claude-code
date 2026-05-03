from llm.client import chat,TOOLS
from util.util import TOOL_HANDLERS,SetTool
from util.message_bus import VALID_MSG_TYPES,BUS
from util.util import extract_text
import json
from pathlib import Path
from util.teammate_manager import TEAM

WORKDIR = Path.cwd()
TEAM_DIR = WORKDIR / ".team"
INBOX_DIR = TEAM_DIR / "inbox"
TEAM_SYSTEM = f"You are a team lead at {WORKDIR}. Spawn teammates and communicate via inboxes."

# 处理用户的一次对话
def agent_loop(history: list, count: int, sub_count: int):  
    # 打印对话次数
    print(f"\n======对话轮次：{count}======\n")
    while True:
        # 打印对话次数和当前调用ai次数
        print(f"\n======对话轮次：{count}，当前轮对话调用ai次数：{sub_count}======\n")
        inbox = BUS.read_inbox("lead")
        if inbox:
            messages.append({
                "role": "user",
                "content": f"<inbox>{json.dumps(inbox, indent=2)}</inbox>",
            })

        response = chat(history, system_prompt=TEAM_SYSTEM,tools=TEAMMATE_TOOLS)
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

TEAMMATE_TOOLS = TOOLS + [
    {"name": "spawn_teammate", "description": "Spawn a persistent teammate that runs in its own thread.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "role": {"type": "string"}, "prompt": {"type": "string"}}, "required": ["name", "role", "prompt"]}},
    {"name": "list_teammates", "description": "List all teammates with name, role, status.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "send_message", "description": "Send a message to a teammate's inbox.",
     "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "content": {"type": "string"}, "msg_type": {"type": "string", "enum": list(VALID_MSG_TYPES)}}, "required": ["to", "content"]}},
    {"name": "read_inbox", "description": "Read and drain the lead's inbox.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "broadcast", "description": "Send a message to all teammates.",
     "input_schema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},
]




if __name__ == "__main__":
    SetTool("spawn_teammate", lambda **kw: TEAM.spawn(kw["name"], kw["role"], kw["prompt"]))
    SetTool("list_teammates", lambda **kw: TEAM.list_all())
    SetTool("send_message", lambda **kw: BUS.send("lead", kw["to"], kw["content"], kw.get("msg_type", "message")))
    SetTool("read_inbox", lambda **kw: json.dumps(BUS.read_inbox("lead"), indent=2))
    SetTool("broadcast", lambda **kw: BUS.broadcast("lead", kw["content"], TEAM.member_names()))
    
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

        if query.strip() == "/team":
            print(TEAM.list_all())
            continue
        if query.strip() == "/inbox":
            print(json.dumps(BUS.read_inbox("lead"), indent=2))
            continue

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