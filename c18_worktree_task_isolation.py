from llm.client import chat,TOOLS
from util.util import TOOL_HANDLERS,SetTool,claim_task
from util.message_bus import VALID_MSG_TYPES,BUS
from util.util import extract_text
import json
from pathlib import Path
from util.teammate_manager import TEAM
from util.request_store import REQUEST_STORE
import uuid
import time
import threading
from util.task import TASKS
from util.worktree_manager import WORKTREES


WORKDIR = Path.cwd()
TEAM_DIR = WORKDIR / ".team"
INBOX_DIR = TEAM_DIR / "inbox"
TEAM_SYSTEM = f"You are a team lead at {WORKDIR}. Spawn teammates and communicate via inboxes."
TASKS_DIR = WORKDIR / ".tasks"


WORKTREE_SYSTEM_SYSTEM = (
    f"You are a coding agent at {WORKDIR}. "
    "Use task + worktree tools for multi-task work. "
    "For parallel or risky changes: create tasks, allocate worktree lanes, "
    "run commands in those lanes, then choose keep/remove for closeout."
)

# -- Lead-specific protocol handlers --
def handle_shutdown_request(teammate: str) -> str:
    req_id = str(uuid.uuid4())[:8]
    REQUEST_STORE.create({
        "request_id": req_id,
        "kind": "shutdown",
        "from": "lead",
        "to": teammate,
        "status": "pending",
        "created_at": time.time(),
        "updated_at": time.time(),
    })
    BUS.send(
        "lead", teammate, "Please shut down gracefully.",
        "shutdown_request", {"request_id": req_id},
    )
    return f"Shutdown request {req_id} sent to '{teammate}' (status: pending)"

def handle_plan_review(request_id: str, approve: bool, feedback: str = "") -> str:
    req = REQUEST_STORE.get(request_id)
    if not req:
        return f"Error: Unknown plan request_id '{request_id}'"
    REQUEST_STORE.update(
        request_id,
        status="approved" if approve else "rejected",
        reviewed_by="lead",
        resolved_at=time.time(),
        feedback=feedback,
    )
    BUS.send(
        "lead", req["from"], feedback, "plan_approval_response",
        {"request_id": request_id, "approve": approve, "feedback": feedback},
    )
    return f"Plan {'approved' if approve else 'rejected'} for '{req['from']}'"


def check_shutdown_status(request_id: str) -> str:
    return json.dumps(REQUEST_STORE.get(request_id) or {"error": "not found"})


# 处理用户的一次对话
def agent_loop(history: list, count: int, sub_count: int):  
    # 打印对话次数
    print(f"\n======对话轮次：{count}======\n")
    while True:
        # 打印对话次数和当前调用ai次数
        print(f"\n======对话轮次：{count}，当前轮对话调用ai次数：{sub_count}======\n")
        inbox = BUS.read_inbox("lead")
        if inbox:
            history.append({
                "role": "user",
                "content": f"<inbox>{json.dumps(inbox, indent=2)}</inbox>",
            })

        response = chat(history, system_prompt=WORKTREE_SYSTEM_SYSTEM,tools=TEAMMATE_TOOLS)
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
    {"name": "task_create", "description": "Create a new task.",
     "input_schema": {"type": "object", "properties": {"subject": {"type": "string"}, "description": {"type": "string"}}, "required": ["subject"]}},
    {"name": "task_update", "description": "Update a task's status, owner, or dependencies.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "deleted"]}, "owner": {"type": "string", "description": "Set when a teammate claims the task"}, "blocks": {"type": "array", "items": {"type": "integer"}}, "add_blocks": {"type": "array", "items": {"type": "integer"}}}, "required": ["task_id"]}},
    {"name": "task_list", "description": "List all tasks with status summary.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "task_get", "description": "Get full details of a task by ID.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]}},

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
    {"name": "shutdown_request", "description": "Request a teammate to shut down gracefully. Returns a request_id for tracking.",
     "input_schema": {"type": "object", "properties": {"teammate": {"type": "string"}}, "required": ["teammate"]}},
    {"name": "shutdown_response", "description": "Check the status of a shutdown request by request_id.",
     "input_schema": {"type": "object", "properties": {"request_id": {"type": "string"}}, "required": ["request_id"]}},
    {"name": "plan_approval", "description": "Approve or reject a teammate's plan. Provide request_id + approve + optional feedback.",
     "input_schema": {"type": "object", "properties": {"request_id": {"type": "string"}, "approve": {"type": "boolean"}, "feedback": {"type": "string"}}, "required": ["request_id", "approve"]}},
    {"name": "idle", "description": "Enter idle state (for lead -- rarely used).",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "claim_task", "description": "Claim a task from the board by ID.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]}},
     
     {"name": "task_bind_worktree", "description": "Bind a task to a worktree name.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}, "worktree": {"type": "string"}, "owner": {"type": "string"}}, "required": ["task_id", "worktree"]}},
    {"name": "worktree_create", "description": "Create a git worktree and optionally bind it to a task.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "task_id": {"type": "integer"}, "base_ref": {"type": "string"}}, "required": ["name"]}},
    {"name": "worktree_list", "description": "List worktrees tracked in .worktrees/index.json.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "worktree_enter", "description": "Enter or reopen a worktree lane before working in it.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "worktree_status", "description": "Show git status for one worktree.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "worktree_run", "description": "Run a shell command in a named worktree directory.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "command": {"type": "string"}}, "required": ["name", "command"]}},
    {"name": "worktree_closeout", "description": "Close out a lane by keeping it for follow-up or removing it.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "action": {"type": "string", "enum": ["keep", "remove"]}, "reason": {"type": "string"}, "force": {"type": "boolean"}, "complete_task": {"type": "boolean"}}, "required": ["name", "action"]}},
    {"name": "worktree_remove", "description": "Remove a worktree and optionally mark its bound task completed.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "force": {"type": "boolean"}, "complete_task": {"type": "boolean"}, "reason": {"type": "string"}}, "required": ["name"]}},
    {"name": "worktree_keep", "description": "Mark a worktree as kept without removing it.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "worktree_events", "description": "List recent lifecycle events.",
     "input_schema": {"type": "object", "properties": {"limit": {"type": "integer"}}}},
]


if __name__ == "__main__":
    # 初始化任务管理器
    SetTool("task_create", lambda **kw: TASKS.create(**kw))
    SetTool("task_get", lambda **kw: TASKS.get(**kw))
    SetTool("task_update", lambda **kw: TASKS.update(**kw))
    SetTool("task_list", lambda **kw: TASKS.list_all())

    SetTool("spawn_teammate", lambda **kw: TEAM.spawn(kw["name"], kw["role"], kw["prompt"]))
    SetTool("list_teammates", lambda **kw: TEAM.list_all())
    SetTool("send_message", lambda **kw: BUS.send("lead", kw["to"], kw["content"], kw.get("msg_type", "message")))
    SetTool("read_inbox", lambda **kw: json.dumps(BUS.read_inbox("lead"), indent=2))
    SetTool("broadcast", lambda **kw: BUS.broadcast("lead", kw["content"], TEAM.member_names()))
    
    # 增加shutdown_request,shutdown_response,plan_approval工具
    SetTool("shutdown_request", lambda **kw: handle_shutdown_request(kw["teammate"]))
    SetTool("shutdown_response", lambda **kw: check_shutdown_status(kw.get("request_id", "")))
    SetTool("plan_approval", lambda **kw: handle_plan_review(kw["request_id"], kw["approve"], kw.get("feedback", "")))

    SetTool("idle", lambda **kw: "Lead does not idle.")
    SetTool("claim_task", lambda **kw: claim_task(kw["task_id"], "lead"))

    # worktree
    SetTool("task_bind_worktree", lambda **kw: TASKS.bind_worktree(kw["task_id"], kw["worktree"], kw.get("owner", "")))
    SetTool("worktree_create", lambda **kw: WORKTREES.create(kw["name"], kw.get("task_id"), kw.get("base_ref", "HEAD")))
    SetTool("worktree_list", lambda **kw: WORKTREES.list_all())
    SetTool("worktree_enter", lambda **kw: WORKTREES.enter(kw["name"]))
    SetTool("worktree_status", lambda **kw: WORKTREES.status(kw["name"]))
    SetTool("worktree_run", lambda **kw: WORKTREES.run(kw["name"], kw["command"]))
    SetTool("worktree_closeout", lambda **kw: WORKTREES.closeout(
        kw["name"],
        kw["action"],
        kw.get("reason", ""),
        kw.get("force", False),
        kw.get("complete_task", False),
    ))
    SetTool("worktree_keep", lambda **kw: WORKTREES.keep(kw["name"]))
    SetTool("worktree_remove", lambda **kw: WORKTREES.remove(
        kw["name"],
        kw.get("force", False),
        kw.get("complete_task", False),
        kw.get("reason", ""),
    ))
    SetTool("worktree_events", lambda **kw: EVENTS.list_recent(kw.get("limit", 20)))
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

        if query.strip() == "/tasks":
            TASKS_DIR.mkdir(exist_ok=True)
            for f in sorted(TASKS_DIR.glob("task_*.json")):
                t = json.loads(f.read_text())
                marker = {"pending": "[[咖啡]]", "in_progress": "[🔄]", "completed": "[✅]"}.get(t["status"], "[?]")
                owner = f" @{t['owner']}" if t.get("owner") else ""
                print(f"  {marker} #{t['id']}: {t['subject']}{owner}")
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