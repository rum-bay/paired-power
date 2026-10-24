"""Natural-language paired-power agent using OpenAI Responses API and local MCP stdio."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-6-astra")
API_URL = "https://api.openai.com/v1/responses"
MAX_TOOL_ROUNDS = 4

INSTRUCTIONS = """You are a careful paired-sample t-test power assistant. Respond in the user's language.
Only calculate the paired t-test family using the paired_power_calculate tool. Use exactly one supported mode:
- a-priori: find how many matched pairs are needed for target power
- post-hoc: compute achieved power for a supplied number of pairs
- compromise: compute balanced alpha/beta using beta_alpha_ratio
- criterion: compute alpha for target power and a supplied number of pairs
- sensitivity: find dz for target power and a supplied number of pairs

Never invent or assume tails, dz, alpha, power, n_total, or beta_alpha_ratio. If a needed value is missing or ambiguous, ask the user instead of calling the tool. Clarify whether N means matched pairs when that is ambiguous. The tool's n_total is the number of matched pairs; it is not the number of individual observations. Call the calculator only when the required values are clear. Report numeric outputs from the tool without changing their values, and explain N as pairs."""


class AgentError(RuntimeError):
    pass


class McpClient:
    """Small MCP stdio client for this server's handshake-era protocol."""

    def __init__(self, server_path: Path):
        self.server_path = server_path
        self.process: subprocess.Popen[str] | None = None
        self._request_id = 0

    def __enter__(self) -> "McpClient":
        self.process = subprocess.Popen(
            [sys.executable, "-u", str(self.server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        try:
            response = self.request("initialize", {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "paired-power-agent", "version": "1.0.0"},
            })
            if response.get("protocolVersion") not in {"2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"}:
                raise AgentError("MCP server negotiated an unsupported protocol version")
            self.notify("notifications/initialized")
            return self
        except Exception:
            self.__exit__(*sys.exc_info())
            raise

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        process = self.process
        if process is None:
            return
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)

    def _send(self, message: dict[str, Any]) -> None:
        if self.process is None or self.process.stdin is None:
            raise AgentError("MCP server is not running")
        self.process.stdin.write(json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.process is None or self.process.stdout is None:
            raise AgentError("MCP server is not running")
        self._request_id += 1
        request_id = self._request_id
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)
        line = self.process.stdout.readline()
        if not line:
            code = self.process.poll()
            raise AgentError(f"MCP server closed stdout unexpectedly (exit code {code})")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AgentError("MCP server returned invalid JSON-RPC") from exc
        if not isinstance(response, dict) or response.get("id") != request_id:
            raise AgentError("MCP server returned a mismatched request id")
        if "error" in response:
            error = response["error"]
            raise AgentError(f"MCP {method} failed: {error.get('message', 'unknown error')}")
        result = response.get("result")
        if not isinstance(result, dict):
            raise AgentError(f"MCP {method} returned no result object")
        return result

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)

    def list_tools(self) -> list[dict[str, Any]]:
        result = self.request("tools/list")
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise AgentError("MCP server did not return a tools list")
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content", [])
        if not isinstance(content, list) or not content or not isinstance(content[0], dict):
            raise AgentError("MCP tool returned no text content")
        text = content[0].get("text", "")
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            payload = {"result": text}
        if not isinstance(payload, dict):
            payload = {"result": payload}
        return payload, bool(result.get("isError", False))


def _openai_tool(mcp_tool: dict[str, Any]) -> dict[str, Any]:
    """Convert MCP JSON Schema into strict Responses function schema."""
    schema = mcp_tool.get("inputSchema")
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise AgentError("MCP tool has no object input schema")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise AgentError("MCP tool input schema properties are invalid")
    required_in_mcp = set(schema.get("required", []))
    strict_properties: dict[str, Any] = {}
    for name, definition in properties.items():
        prop = dict(definition)
        if name not in required_in_mcp:
            value_type = prop.get("type")
            if isinstance(value_type, str):
                prop["type"] = [value_type, "null"]
        strict_properties[name] = prop
    strict_schema = {
        "type": "object",
        "properties": strict_properties,
        "required": list(properties),
        "additionalProperties": False,
    }
    return {
        "type": "function",
        "name": mcp_tool["name"],
        "description": mcp_tool.get("description", ""),
        "parameters": strict_schema,
        "strict": True,
    }


def _responses_api_request(payload: dict[str, Any]) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise AgentError("Set OPENAI_API_KEY in this terminal to use the AI agent; the MCP server works without it.")
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        try:
            error_obj = json.loads(details).get("error", {})
            detail = error_obj.get("message", f"HTTP {exc.code}")
        except (json.JSONDecodeError, AttributeError):
            detail = f"HTTP {exc.code}"
        raise AgentError(f"OpenAI Responses API error: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AgentError(f"Could not reach the OpenAI Responses API: {exc.reason}") from exc
    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise AgentError("OpenAI Responses API returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise AgentError("OpenAI Responses API returned an unexpected response")
    return result


def _response_text(response: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") in {"output_text", "refusal"}:
                text = content.get("text")
                if isinstance(text, str):
                    chunks.append(text)
    return "\n".join(chunks).strip()


def run_agent(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    api_request: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    server_path: Path | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Run one natural-language request and return the final text and tool results."""
    if not prompt.strip():
        raise AgentError("Provide a natural-language request")
    api_request = api_request or _responses_api_request
    server_path = server_path or ROOT / "mcp_server.py"
    tool_results: list[dict[str, Any]] = []

    with McpClient(server_path) as mcp:
        available_tools = mcp.list_tools()
        if not available_tools:
            raise AgentError("MCP server exposed no tools")
        api_tools = [_openai_tool(tool) for tool in available_tools]
        conversation: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        for _ in range(MAX_TOOL_ROUNDS):
            response = api_request({
                "model": model,
                "instructions": INSTRUCTIONS,
                "input": conversation,
                "tools": api_tools,
                "tool_choice": "auto",
            })
            output = response.get("output", [])
            if not isinstance(output, list):
                raise AgentError("The model returned an invalid output list")
            calls = [item for item in output if isinstance(item, dict) and item.get("type") == "function_call"]
            if not calls:
                text = _response_text(response)
                if not text:
                    raise AgentError("The model returned neither a tool call nor a text answer")
                return text, tool_results

            # Responses API requires the assistant output items to be returned with tool results.
            conversation.extend(output)
            for call in calls:
                name = call.get("name")
                call_id = call.get("call_id")
                arguments: dict[str, Any] = {}
                try:
                    parsed_arguments = json.loads(call.get("arguments", "{}"))
                    if not isinstance(parsed_arguments, dict):
                        raise ValueError("tool arguments must be an object")
                    arguments = {key: value for key, value in parsed_arguments.items() if value is not None}
                    if name not in {tool["name"] for tool in available_tools}:
                        raise ValueError(f"unknown requested tool: {name}")
                    result, is_error = mcp.call_tool(name, arguments)
                except (json.JSONDecodeError, ValueError, AgentError) as exc:
                    result, is_error = {"error": str(exc), "code": "INVALID_VALUE"}, True
                tool_results.append({"name": name, "arguments": arguments, "result": result, "isError": is_error})
                conversation.append({
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps({"isError": is_error, **result}, separators=(",", ":"), ensure_ascii=False),
                })
        raise AgentError("The model exceeded the allowed number of calculator tool rounds")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Ask for a paired t-test power calculation in natural language.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI Responses API model (default: OPENAI_MODEL or gpt-6-astra)")
    parser.add_argument("request", nargs="+", help="Natural-language calculation request")
    args = parser.parse_args(argv)
    try:
        answer, tool_results = run_agent(" ".join(args.request), model=args.model)
    except AgentError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    for result in tool_results:
        print("MCP result: " + json.dumps(result["result"], ensure_ascii=False), file=sys.stderr)
    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())