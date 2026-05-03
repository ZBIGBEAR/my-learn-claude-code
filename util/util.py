import subprocess
import os,datetime,time
from pathlib import Path
WORKDIR = Path.cwd()

def execute_tool_calls(response_content) -> list[dict]:
    results = []
    for block in response_content:
        if block.type != "tool_use":
            continue
        command = block.input["command"]
        output = run_bash(command)
        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": output,
        })
    return results

def extract_text(content) -> str:
    if not isinstance(content, list):
        return ""
    texts = []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            texts.append(f"文本内容：{text}\n")
        elif block.type == "thinking":
            texts.append(f"思考内容：{block.thinking}\n")
    return "\n".join(texts).strip()

def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(item in command for item in dangerous):
        return "Error: Dangerous command blocked"
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"
    except (FileNotFoundError, OSError) as e:
        return f"Error: {e}"

    output = (result.stdout + result.stderr).strip()
    return output[:50000] if output else "(no output)"


def run_read(path: str, limit: int = None) -> str:
    try:
        text = safe_path(path).read_text()
        lines = text.splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = safe_path(path)
        content = fp.read_text()
        if old_text not in content:
            return f"Error: Text not found in {path}"
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"

def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path

TOOL_HANDLERS = {
    "bash": lambda **kw: run_bash(kw["command"]),
    "read_file": lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file": lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    # "todo": lambda **kw: TODO.update(kw["items"]),
    "compact":    lambda **kw: compact_history(),
}


def compact_history():
    return "Compacting conversation..."

def SetTool(name,args):
    TOOL_HANDLERS[name] = args

# 检查cron表达式是否匹配给定的datetime
def cron_matches(expr: str, dt: datetime) -> bool:
    """
    Check if a 5-field cron expression matches a given datetime.

    Fields: minute hour day-of-month month day-of-week
    Supports: * (any), */N (every N), N (exact), N-M (range), N,M (list)

    No external dependencies -- simple manual matching.
    """
    fields = expr.strip().split()
    if len(fields) != 5:
        return False

    values = [dt.minute, dt.hour, dt.day, dt.month, dt.weekday()]
    # Python weekday: 0=Monday; cron: 0=Sunday. Convert.
    cron_dow = (dt.weekday() + 1) % 7
    values[4] = cron_dow
    ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]

    for field, value, (lo, hi) in zip(fields, values, ranges):
        if not _field_matches(field, value, lo, hi):
            return False
    return True

# 检查cron表达式字段是否匹配给定值
def _field_matches(field: str, value: int, lo: int, hi: int) -> bool:
    """Match a single cron field against a value."""
    if field == "*":
        return True

    for part in field.split(","):
        # Handle step: */N or N-M/S
        step = 1
        if "/" in part:
            part, step_str = part.split("/", 1)
            step = int(step_str)

        if part == "*":
            # */N -- check if value is on the step grid
            if (value - lo) % step == 0:
                return True
        elif "-" in part:
            # Range: N-M
            start, end = part.split("-", 1)
            start, end = int(start), int(end)
            if start <= value <= end and (value - start) % step == 0:
                return True
        else:
            # Exact value
            if int(part) == value:
                return True

    return False