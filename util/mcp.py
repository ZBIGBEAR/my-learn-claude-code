import os
import subprocess
import json
from pathlib import Path
from typing import Any

WORKDIR = Path.cwd()


class MCPClient:
    """
    MCP client supporting both stdio and HTTP transports.

    Handles configurations from plugin.json:
    - stdio: {"command": "npx", "args": ["-y", "..."], "env": {...}}
    - http: {"type": "http", "url": "https://..."}
    """

    def __init__(
        self,
        server_name: str,
        command: str = None,
        args: list = None,
        env: dict = None,
        transport: str = "stdio",
        url: str = None,
    ):
        self.server_name = server_name
        self.command = command
        self.args = args or []
        self.env = {**os.environ, **(env or {})}
        self.transport = transport
        self.url = url
        self.process = None
        self._request_id = 0
        self._tools = []
        self._initialized = False

    @classmethod
    def from_config(cls, server_name: str, config: dict):
        """Create client from plugin.json config."""
        transport_type = config.get("type", "stdio")
        if transport_type == "http":
            return cls(
                server_name=server_name,
                transport="http",
                url=config.get("url"),
            )
        return cls(
            server_name=server_name,
            command=config.get("command"),
            args=config.get("args", []),
            env=config.get("env"),
            transport="stdio",
        )

    def connect(self) -> bool:
        """Start the MCP server or establish HTTP connection."""
        if self.transport == "http":
            return self._connect_http()
        return self._connect_stdio()

    def _connect_stdio(self) -> bool:
        """Start the MCP server process via stdio."""
        try:
            self.process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.env,
                text=True,
            )
            self._send_stdio({
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "teaching-agent", "version": "1.0"},
                },
            })
            response = self._recv_stdio()
            if response and "result" in response:
                self._send_stdio({"method": "notifications/initialized"})
                self._initialized = True
                return True
        except FileNotFoundError:
            print(f"[MCP] Server command not found: {self.command}")
        except Exception as e:
            print(f"[MCP] Connection failed: {e}")
        return False

    def _connect_http(self) -> bool:
        """Connect via HTTP transport."""
        import urllib.request
        import urllib.error
        self._initialized = True
        return True

    def list_tools(self) -> list:
        """Fetch available tools from the server."""
        if self.transport == "http":
            return self._list_tools_http()
        return self._list_tools_stdio()

    def _list_tools_stdio(self) -> list:
        """List tools via stdio."""
        self._send_stdio({"method": "tools/list", "params": {}})
        response = self._recv_stdio()
        if response and "error" in response:
            print(f"[MCP] Error listing tools: {response['error'].get('message', 'unknown')},method:tools/list")
        elif response and "result" in response:
            self._tools = response["result"].get("tools", [])
        return self._tools

    def _list_tools_http(self) -> list:
        """List tools via HTTP."""
        import urllib.request
        import json as _json
        try:
            data = _json.dumps({"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1})
            req = urllib.request.Request(self.url, data=data.encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as resp:
                data = _json.loads(resp.read())
                if "result" in data:
                    self._tools = data["result"].get("tools", [])
        except Exception as e:
            print(f"[MCP] HTTP list tools error: {e}")
        return self._tools

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool on the server."""
        if self.transport == "http":
            return self._call_tool_http(tool_name, arguments)
        return self._call_tool_stdio(tool_name, arguments)

    def _call_tool_stdio(self, tool_name: str, arguments: dict) -> str:
        """Call tool via stdio."""
        self._send_stdio({
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        })
        response = self._recv_stdio()
        if response and "result" in response:
            content = response["result"].get("content", [])
            return "\n".join(c.get("text", str(c)) for c in content)
        if response and "error" in response:
            return f"MCP Error: {response['error'].get('message', 'unknown')}, tool: {tool_name}"
        return "MCP Error: no response"

    def _call_tool_http(self, tool_name: str, arguments: dict) -> str:
        """Call tool via HTTP."""
        import urllib.request
        import urllib.error
        import json as _json
        try:
            data = _json.dumps({
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
                "id": 1,
            })
            req = urllib.request.Request(self.url, data=data.encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as resp:
                data = _json.loads(resp.read())
                if "result" in data:
                    content = data["result"].get("content", [])
                    return "\n".join(c.get("text", str(c)) for c in content)
                if "error" in data:
                    return f"MCP Error HTTP: {data['error'].get('message', 'unknown')}"
        except Exception as e:
            return f"MCP Error: {e}"
        return "MCP Error: no response"

    def get_agent_tools(self) -> list:
        """Convert MCP tools to agent tool format."""
        agent_tools = []
        for tool in self._tools:
            prefixed_name = f"mcp__{self.server_name}__{tool['name']}"
            input_schema = tool.get("inputSchema", tool.get("input_schema", {}))
            agent_tools.append({
                "name": prefixed_name,
                "description": tool.get("description", ""),
                "input_schema": input_schema,
                "_mcp_server": self.server_name,
                "_mcp_tool": tool["name"],
            })
        return agent_tools

    def disconnect(self):
        """Shut down the server connection."""
        if self.transport == "stdio":
            self._disconnect_stdio()
        else:
            self._disconnect_http()

    def _disconnect_stdio(self):
        """Disconnect stdio process."""
        if self.process:
            try:
                self._send_stdio({"method": "shutdown"})
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
            self.process = None

    def _disconnect_http(self):
        """Disconnect HTTP (no-op for urllib)."""
        pass

    def _send_stdio(self, message: dict):
        if not self.process or self.process.poll() is not None:
            return
        self._request_id += 1
        envelope = {"jsonrpc": "2.0", "id": self._request_id, **message}
        line = json.dumps(envelope) + "\n"
        try:
            self.process.stdin.write(line)
            self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def _recv_stdio(self) -> dict | None:
        if not self.process or self.process.poll() is not None:
            return None
        try:
            line = self.process.stdout.readline()
            if line:
                return json.loads(line)
        except (json.JSONDecodeError, OSError):
            pass
        return None

class PluginLoader:
    """Load plugins from .claude-plugin/ directories."""

    def __init__(self, search_dirs: list = None):
        self.search_dirs = search_dirs or [WORKDIR]
        self.plugins = {}

    def scan(self) -> list:
        """Scan directories for .claude-plugin/plugin.json manifests."""
        found = []
        for search_dir in self.search_dirs:
            # 加载search_dir目录下所有*.json文件
            for json_path in Path(search_dir).glob("*.json"):
                if json_path.is_file():
                    try:
                        manifest = json.loads(json_path.read_text())
                        mcp_count = 0
                        for server_name, config in manifest.get("mcpServers", {}).items():
                            self.plugins[server_name] = config
                            found.append(server_name)
                            mcp_count+=1
                        
                        print(f"Scanning {json_path},find {mcp_count} mcp servers\n")
                    except (json.JSONDecodeError, OSError) as e:
                        print(f"[Plugin] Failed to load {json_path}: {e}")

        return found

    def get_mcp_servers(self) -> dict:
        """Extract MCP server configs from loaded plugins."""
        servers = {}
        for plugin_name, config in self.plugins.items():
            servers[plugin_name] = {
                "command": config.get("command"),
                "args": config.get("args", []),
                "env": config.get("env"),
                "type": config.get("type"),
                "url": config.get("url"),
                "description": config.get("description", ""),
            }
        return servers

MCPPluginLoader = PluginLoader([WORKDIR / ".claude_plugin"])

class MCPToolRouter:
    """
    Routes tool calls to the correct MCP server.

    MCP tools are prefixed mcp__{server}__{tool} and live alongside
    native tools in the same tool pool. The router strips the prefix
    and dispatches to the right MCPClient.
    """

    def __init__(self):
        self.clients = {}  # server_name -> MCPClient

    def register_client(self, client: MCPClient):
        self.clients[client.server_name] = client

    def is_mcp_tool(self, tool_name: str) -> bool:
        return tool_name.startswith("mcp__")

    def call(self, tool_name: str, arguments: dict) -> str:
        """Route an MCP tool call to the correct server."""
        parts = tool_name.split("__", 2)
        if len(parts) != 3:
            return f"Error: Invalid MCP tool name: {tool_name}"
        _, server_name, actual_tool = parts
        client = self.clients.get(server_name)
        if not client:
            return f"Error: MCP server not found: {server_name}"
        return client.call_tool(actual_tool, arguments)

    def get_all_tools(self) -> list:
        """Collect tools from all connected MCP servers."""
        tools = []
        for client in self.clients.values():
            tools.extend(client.get_agent_tools())
        return tools

MCPRouter = MCPToolRouter()