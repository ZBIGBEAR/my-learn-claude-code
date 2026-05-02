from pathlib import Path
import json
import os
import subprocess

HOOK_EVENTS = ("PreToolUse", "PostToolUse", "SessionStart")
HOOK_TIMEOUT = 30  # seconds
# Real CC timeouts:
#   TOOL_HOOK_EXECUTION_TIMEOUT_MS = 600000 (10 minutes for tool hooks)
#   SESSION_END_HOOK_TIMEOUT_MS = 1500 (1.5 seconds for SessionEnd hooks)
from pathlib import Path

WORKDIR = Path.cwd()
# Workspace trust marker. Hooks only run if this file exists (or SDK mode).
TRUST_MARKER = WORKDIR / ".claude" / ".claude_trusted"


class HookManager:
    """
    Load and execute hooks from .hooks.json configuration.

    The hook manager does three simple jobs:
    - load hook definitions
    - run matching commands for an event
    - aggregate block / message results for the caller
    """

    def __init__(self, config_path: Path = None, sdk_mode: bool = False):
        self.hooks = {"PreToolUse": [], "PostToolUse": [], "SessionStart": []}
        self._sdk_mode = sdk_mode
        config_path = config_path or (WORKDIR / ".hooks.json")
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
                for event in HOOK_EVENTS:
                    self.hooks[event] = config.get("hooks", {}).get(event, [])
                print(f"[Hooks loaded from {config_path},PreHookCount:{len(self.hooks['PreToolUse'])},PostHookCount:{len(self.hooks['PostToolUse'])},SessionStartHookCount:{len(self.hooks['SessionStart'])}]")
            except Exception as e:
                print(f"[Hook config error: {e}]")

    def run_hooks(self, event: str, context: dict = None) -> dict:
        """
        Execute all hooks for an event.

        Returns: {"blocked": bool, "messages": list[str]}
          - blocked: True if any hook returned exit code 1
          - messages: stderr content from exit-code-2 hooks (to inject)
        """
        result = {"blocked": False, "messages": []}

        hooks = self.hooks.get(event, [])

        for hook_def in hooks:
            # Check matcher (tool name filter for PreToolUse/PostToolUse)
            matcher = hook_def.get("matcher")
            if matcher and context:
                tool_name = context.get("tool_name", "")
                if matcher != "*" and matcher != tool_name:
                    continue
            for hook in hook_def.get("hooks", []):
                if hook.get("type","") != "command":
                    continue
                command = hook.get("command", "")
                if not command:
                    continue
                # Build environment with hook context
                env = dict(os.environ)
                if context:
                    env["HOOK_EVENT"] = event
                    env["HOOK_TOOL_NAME"] = context.get("tool_name", "")
                    env["HOOK_TOOL_INPUT"] = json.dumps(
                        context.get("tool_input", {}), ensure_ascii=False)[:10000]
                    if "tool_output" in context:
                        env["HOOK_TOOL_OUTPUT"] = str(
                            context["tool_output"])[:10000]

                try:
                    print(f"[start hook:{event}] {command}")
                    # Execute command
                    r = subprocess.run(
                        command, shell=True, cwd=WORKDIR, env=env,
                        capture_output=True, text=True, timeout=HOOK_TIMEOUT,
                    )

                    if r.returncode == 0:
                        # Continue silently
                        if r.stdout.strip():
                            print(f"  [hook:{event}] {r.stdout.strip()[:100]}")

                        # Optional structured stdout: small extension point that
                        # keeps the teaching contract simple.
                        try:
                            hook_output = json.loads(r.stdout)
                            if "updatedInput" in hook_output and context:
                                context["tool_input"] = hook_output["updatedInput"]
                            if "additionalContext" in hook_output:
                                result["messages"].append(
                                    hook_output["additionalContext"])
                            if "permissionDecision" in hook_output:
                                result["permission_override"] = (
                                    hook_output["permissionDecision"])
                        except (json.JSONDecodeError, TypeError):
                            pass  # stdout was not JSON -- normal for simple hooks

                    elif r.returncode == 1:
                        # Block execution
                        result["blocked"] = True
                        reason = r.stderr.strip() or "Blocked by hook"
                        result["block_reason"] = reason
                        print(f"  [hook:{event}] BLOCKED: {reason[:200]}")

                    elif r.returncode == 2:
                        # Inject message
                        msg = r.stderr.strip()
                        if msg:
                            result["messages"].append(msg)
                            print(f"  [hook:{event}] INJECT: {msg[:200]}")

                except subprocess.TimeoutExpired:
                    print(f"  [hook:{event}] Timeout ({HOOK_TIMEOUT}s)")
                except Exception as e:
                    print(f"  [hook:{event}] Error: {e}")

        return result
