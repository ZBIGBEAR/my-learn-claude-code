from llm.client import chat
from util.util import TOOL_HANDLERS
from anthropic import APIError
from util.util import extract_text,SetTool
from llm.client import TOOLS
from util.memory import MemoryManager
from pathlib import Path
from util.system_prompt import SystemPromptBuilder
import json,random,time


WORKDIR = Path.cwd()

MEMORY_TOOLS = TOOLS + [{"name": "save_memory", "description": "Save a persistent memory that survives across sessions.",
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string", "description": "Short identifier (e.g. prefer_tabs, db_schema)"},
         "description": {"type": "string", "description": "One-line summary of what this memory captures"},
         "type": {"type": "string", "enum": ["user", "feedback", "project", "reference"],
                  "description": "user=preferences, feedback=corrections, project=non-obvious project conventions or decision reasons, reference=external resource pointers"},
         "content": {"type": "string", "description": "Full memory content (multi-line OK)"},
     }, "required": ["name", "description", "type", "content"]}},]

# Recovery constants
MAX_RECOVERY_ATTEMPTS = 3
BACKOFF_BASE_DELAY = 1.0  # seconds
BACKOFF_MAX_DELAY = 30.0  # seconds
TOKEN_THRESHOLD = 50000   # chars / 4 ~ tokens for compact trigger

CONTINUATION_MESSAGE = (
    "Output limit hit. Continue directly from where you stopped -- "
    "no recap, no repetition. Pick up mid-sentence if needed."
)

def estimate_tokens(messages: list) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(json.dumps(messages, default=str)) // 4


def auto_compact(messages: list) -> list:
    """
    Compress conversation history into a short continuation summary.
    """
    conversation_text = json.dumps(messages, default=str)[:80000]
    prompt = (
        "Summarize this conversation for continuity. Include:\n"
        "1) Task overview and success criteria\n"
        "2) Current state: completed work, files touched\n"
        "3) Key decisions and failed approaches\n"
        "4) Remaining next steps\n"
        "Be concise but preserve critical details.\n\n"
        + conversation_text
    )
    try:
        response = client.messages.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
        )
        summary = response.content[0].text
    except Exception as e:
        summary = f"(compact failed: {e}). Previous context lost."

    continuation = (
        "This session continues from a previous conversation that was compacted. "
        f"Summary of prior context:\n\n{summary}\n\n"
        "Continue from where we left off without re-asking the user."
    )
    return [{"role": "user", "content": continuation}]


def backoff_delay(attempt: int) -> float:
    """Exponential backoff with jitter: base * 2^attempt + random(0, 1)."""
    delay = min(BACKOFF_BASE_DELAY * (2 ** attempt), BACKOFF_MAX_DELAY)
    jitter = random.uniform(0, 1)
    return delay + jitter


# 处理用户的一次对话
def agent_loop(history: list, count: int, sub_count: int):  
    # 打印对话次数
    print(f"\n======对话轮次：{count}======\n")
    while True:
        # 每次调用大模型，都要重新构建system prompt，因为内存可能会改变
        system = prompt_builder.build()
        # 打印对话次数和当前调用ai次数
        print(f"\n======对话轮次：{count}，当前轮对话调用ai次数：{sub_count}======\n")
        response = None
        for attempt in range(MAX_RECOVERY_ATTEMPTS + 1):
            try:
                response = chat(history, system=system, tools=MEMORY_TOOLS)
            except APIError as e:
                error_body = str(e).lower()

                # Strategy 2: prompt_too_long -> compact and retry
                if "overlong_prompt" in error_body or ("prompt" in error_body and "long" in error_body):
                    print(f"[Recovery] Prompt too long. Compacting... (attempt {attempt + 1})")
                    messages[:] = auto_compact(messages)
                    continue

                # Strategy 3: connection/rate errors -> backoff
                if attempt < MAX_RECOVERY_ATTEMPTS:
                    delay = backoff_delay(attempt)
                    print(f"[Recovery] API error: {e}. "
                          f"Retrying in {delay:.1f}s (attempt {attempt + 1}/{MAX_RECOVERY_ATTEMPTS})")
                    time.sleep(delay)
                    continue

                # All retries exhausted
                print(f"[Error] API call failed after {MAX_RECOVERY_ATTEMPTS} retries: {e}")
                return

            except (ConnectionError, TimeoutError, OSError,Exception) as e:
                # Strategy 3: network-level errors -> backoff
                if attempt < MAX_RECOVERY_ATTEMPTS:
                    delay = backoff_delay(attempt)
                    print(f"[Recovery] Connection error: {e}. "
                          f"Retrying in {delay:.1f}s (attempt {attempt + 1}/{MAX_RECOVERY_ATTEMPTS})")
                    time.sleep(delay)
                    continue

                print(f"[Error] Connection failed after {MAX_RECOVERY_ATTEMPTS} retries: {e}")
                return
        if response is None:
            print("[Error] No response received.")
            return
        # 提取ai回复的文本内容
        print(f"\n======ai回复：{response.content}，stop_reason：{response.stop_reason}======\n")
        history.append({"role": "assistant", "content": response.content})

    # -- Strategy 1: max_tokens recovery --
        if response.stop_reason == "max_tokens":
            max_output_recovery_count += 1
            if max_output_recovery_count <= MAX_RECOVERY_ATTEMPTS:
                print(f"[Recovery] max_tokens hit "
                      f"({max_output_recovery_count}/{MAX_RECOVERY_ATTEMPTS}). "
                      "Injecting continuation...")
                messages.append({"role": "user", "content": CONTINUATION_MESSAGE})
                continue  # retry the loop
            else:
                print(f"[Error] max_tokens recovery exhausted "
                      f"({MAX_RECOVERY_ATTEMPTS} attempts). Stopping.")
                return

        # Reset max_tokens counter on successful non-max_tokens response
        max_output_recovery_count = 0

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
        # Check if we should auto-compact (proactive, not just reactive)
        if estimate_tokens(messages) > TOKEN_THRESHOLD:
            print("[Recovery] Token estimate exceeds threshold. Auto-compacting...")
            messages[:] = auto_compact(messages)

        # 继续执行下一次对话
        sub_count += 1

prompt_builder = SystemPromptBuilder(workdir=WORKDIR, tools=MEMORY_TOOLS)

if __name__ == "__main__":
    # memory_mgr.save_memory有4个参数，分别是name, description, type, content
    # 这里使用lambda表达式，将kw参数展开为4个参数，传递给memory_mgr.save_memory
    # 这样，工具调用时，用户只需要传递name, description, type, content参数，即可保存内存
    # 而不需要传递其他参数
    SetTool("save_memory", lambda **kw: memory_mgr.save_memory(**kw))
    
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

        if query.strip() == "/prompt":
            print("--- System Prompt ---")
            print(prompt_builder.build())
            print("--- End ---")
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