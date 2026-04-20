from llm.client import chat
from util.util import TOOL_HANDLERS

from util.util import extract_text
from util.util import SetTool
from util.todo_manager import TODO



# 处理用户的一次对话
def agent_loop(history: list, count: int, sub_count: int):  
    # 打印对话次数
    print(f"\n======对话轮次：{count}======\n")
    while True:
        used_todo = False
        # 打印对话次数和当前调用ai次数
        print(f"\n======对话轮次：{count}，当前轮对话调用ai次数：{sub_count}======\n")
        
        response = chat(history)
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
                if block.name == "todo":
                    used_todo = True
        # 把工具调用的结果添加到历史记录中
        history.append({"role": "user", "content": results})

        if used_todo:
            print(f"已经调用了todo, 重置计划提醒间隔")
            TODO.state.rounds_since_update = 0
        else:
            TODO.note_round_without_update()
            reminder = TODO.reminder()
            print(f"当前计划提醒：{reminder}")
            if reminder:
                results.insert(0, {"type": "text", "text": reminder})
        # 继续执行下一次对话
        sub_count += 1

if __name__ == "__main__":
    SetTool("todo", TODO.update)

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