
import json
import threading
from pathlib import Path
from llm.client import chat,TOOLS
from util.message_bus import MessageBus,VALID_MSG_TYPES,BUS
from llm.client import chat
from util.util import SetTool,TOOL_HANDLERS

from dotenv import load_dotenv

load_dotenv(override=True)

WORKDIR = Path.cwd()
TEAM_DIR = WORKDIR / ".team"
INBOX_DIR = TEAM_DIR / "inbox"

SYSTEM = f"You are a team lead at {WORKDIR}. Spawn teammates and communicate via inboxes."


# if tool_name == "bash":
#             return _run_bash(args["command"])
#         if tool_name == "read_file":
#             return _run_read(args["path"])
#         if tool_name == "write_file":
#             return _run_write(args["path"], args["content"])
#         if tool_name == "edit_file":
#             return _run_edit(args["path"], args["old_text"], args["new_text"])
#         if tool_name == "send_message":
#             return BUS.send(sender, args["to"], args["content"], args.get("msg_type", "message"))
#         if tool_name == "read_inbox":
#             return json.dumps(BUS.read_inbox(sender), indent=2)
#         return f"Unknown tool: {tool_name}"
TEAM_TOOLS = TOOL_HANDLERS.copy()

# -- TeammateManager: persistent named agents with config.json --
class TeammateManager:
    """Persistent teammate registry plus worker-loop launcher."""

    def __init__(self, team_dir: Path):
        self.dir = team_dir
        self.dir.mkdir(exist_ok=True)
        self.config_path = self.dir / "config.json"
        self.config = self._load_config()
        self.threads = {}

    def _load_config(self) -> dict:
        if self.config_path.exists():
            return json.loads(self.config_path.read_text())
        return {"team_name": "default", "members": []}

    def _save_config(self):
        self.config_path.write_text(json.dumps(self.config, indent=2, ensure_ascii=False), encoding="utf-8")

    def _find_member(self, name: str) -> dict:
        for m in self.config["members"]:
            if m["name"] == name:
                return m
        return None

    def spawn(self, name: str, role: str, prompt: str) -> str:
        member = self._find_member(name)
        if member:
            if member["status"] not in ("idle", "shutdown"):
                return f"Error: '{name}' is currently {member['status']}"
            member["status"] = "working"
            member["role"] = role
        else:
            member = {"name": name, "role": role, "status": "working","prompt": prompt}
            self.config["members"].append(member)
        self._save_config()
        thread = threading.Thread(
            target=self._teammate_loop,
            args=(name, role, prompt),
            daemon=True,
        )
        self.threads[name] = thread
        thread.start()
        return f"Spawned '{name}' (role: {role})"

    def _teammate_loop(self, name: str, role: str, prompt: str):
        sys_prompt = (
            f"You are '{name}', role: {role}, at {WORKDIR}. "
            f"Use send_message to communicate. Complete your task."
        )
        messages = [{"role": "user", "content": prompt}]
        tools = self._teammate_tools()
        for _ in range(50):
            inbox = BUS.read_inbox(name)
            for msg in inbox:
                messages.append({"role": "user", "content": json.dumps(msg)})
            try:
                response  = chat(messages=messages, system_prompt=sys_prompt, tools=tools, max_tokens=8000)
            except Exception:
                break
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                break
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    output = self._exec(name, block.name, block.input)
                    print(f"  [{name}] {block.name}: {str(output)[:120]}")
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(output),
                    })
            messages.append({"role": "user", "content": results})
        member = self._find_member(name)
        if member and member["status"] != "shutdown":
            member["status"] = "idle"
            self._save_config()

    def _exec(self, sender: str, tool_name: str, args: dict) -> str:
        # these base tools are unchanged from s02
        handler = TEAM_TOOLS.get(tool_name)
        if handler:
            return handler(**args)
        elif tool_name == "send_message":
            return BUS.send(sender, args["to"], args["content"], args.get("msg_type", "message"))
        elif tool_name == "read_inbox":
            return json.dumps(BUS.read_inbox(sender), indent=2)
        return f"Unknown tool: {tool_name}"
    def _teammate_tools(self) -> list:
        # these base tools are unchanged from s02
        return TOOLS + [
            {"name": "send_message", "description": "Send message to a teammate.",
             "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "content": {"type": "string"}, "msg_type": {"type": "string", "enum": list(VALID_MSG_TYPES)}}, "required": ["to", "content"]}},
            {"name": "read_inbox", "description": "Read and drain your inbox.",
             "input_schema": {"type": "object", "properties": {}}},
        ]

    def list_all(self) -> str:
        if not self.config["members"]:
            return "No teammates."
        lines = [f"Team: {self.config['team_name']}"]
        for m in self.config["members"]:
            lines.append(f"  {m['name']} ({m['role']}): {m['status']}")
        return "\n".join(lines)

    def member_names(self) -> list:
        return [m["name"] for m in self.config["members"]]


# 团队管理器
TEAM = TeammateManager(TEAM_DIR)