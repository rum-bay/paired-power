"""Minimal stdio MCP server for the paired-power engine (standard library only)."""
from __future__ import annotations

import json
import sys
from typing import Any

import gpower_clone
import paired_power


SERVER_NAME = "paired-power"
SERVER_VERSION = "1.0.0"
MAX_FRAME_BYTES = 1_048_576
SUPPORTED_PROTOCOLS = {
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
}

_MODE_FIELDS = {
    "a-priori": ["tails", "dz", "alpha", "power"],
    "post-hoc": ["tails", "dz", "alpha", "n_total"],
    "compromise": ["tails", "dz", "beta_alpha_ratio", "n_total"],
    "criterion": ["tails", "dz", "power", "n_total"],
    "sensitivity": ["tails", "alpha", "power", "n_total"],
}

_TOOL = {
    "name": "paired_power_calculate",
    "description": (
        "Calculate paired-sample t-test power or required sample size. "
        "n_total means number of matched pairs, not individual participants. "
        "Supported modes are a-priori, post-hoc, compromise, criterion, and sensitivity. "
        "Supply exactly the fields required by the selected mode; do not invent missing values."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": list(_MODE_FIELDS),
                "description": "One of the five supported analysis modes.",
            },
            "tails": {
                "type": "integer",
                "enum": [1, 2],
                "description": "1 for one-tailed, 2 for two-tailed.",
            },
            "dz": {
                "type": "number",
                "description": "Positive paired standardized effect size, required except in sensitivity mode.",
            },
            "alpha": {
                "type": "number",
                "description": "Significance level; required except in a-priori and criterion modes.",
            },
            "power": {
                "type": "number",
                "description": "Target power in a-priori, criterion, and sensitivity modes.",
            },
            "n_total": {
                "type": "integer",
                "description": "Number of matched pairs; required in all modes except a-priori.",
            },
            "beta_alpha_ratio": {
                "type": "number",
                "description": "Type-II/type-I error ratio; required in compromise mode.",
            },
        },
        "required": ["mode", "tails"],
        "additionalProperties": False,
    },
    "annotations": {
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
    },
}


def _json_line(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _rpc_error(request_id: Any, code: int, message: str) -> None:
    _json_line({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    })


def _tool_result(payload: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{
            "type": "text",
            "text": json.dumps(payload, separators=(",", ":"), ensure_ascii=False, allow_nan=False),
        }],
        "isError": is_error,
    }


def _as_cli_values(arguments: dict[str, Any]) -> dict[str, str]:
    values = {"test": "t-paired"}
    for key, value in arguments.items():
        if key == "test":
            raise gpower_clone.CliError("Parameter test is not accepted by this tool", "UNKNOWN_PARAM", "test")
        if isinstance(value, (dict, list)) or value is None:
            raise gpower_clone.CliError("Expected a scalar value", "INVALID_VALUE", key)
        if isinstance(value, bool):
            raw = "true" if value else "false"
        else:
            raw = str(value)
        values[key] = raw
    return values


def _call_tool(params: Any) -> dict[str, Any]:
    if not isinstance(params, dict):
        return _tool_result({"error": "Expected an object of tool parameters", "code": "INVALID_VALUE"}, is_error=True)
    name = params.get("name")
    if name != _TOOL["name"]:
        return _tool_result({"error": "Unknown tool", "code": "UNSUPPORTED"}, is_error=True)
    arguments = params.get("arguments", {})
    if not isinstance(arguments, dict):
        return _tool_result({"error": "Tool arguments must be an object", "code": "INVALID_VALUE"}, is_error=True)
    try:
        mode, values = gpower_clone.validate(_as_cli_values(arguments))
        result = paired_power.calculate(mode, values)
        return _tool_result(result)
    except gpower_clone.CliError as exc:
        error: dict[str, str] = {"error": str(exc), "code": exc.code}
        if exc.field is not None:
            error["field"] = exc.field
        return _tool_result(error, is_error=True)
    except paired_power.NoSolutionError as exc:
        return _tool_result({"error": str(exc), "code": "NO_SOLUTION"}, is_error=True)
    except Exception:
        return _tool_result({"error": "Unexpected internal error", "code": "INTERNAL_ERROR"}, is_error=True)


def _handle(message: Any) -> None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        _rpc_error(None, -32600, "Invalid JSON-RPC request")
        return
    method = message.get("method")
    if not isinstance(method, str):
        _rpc_error(message.get("id"), -32600, "Missing JSON-RPC method")
        return
    request_id = message.get("id")
    has_id = "id" in message
    params = message.get("params", {})

    if method in {"notifications/initialized", "notifications/cancelled"}:
        return
    if method == "ping":
        if has_id:
            _json_line({"jsonrpc": "2.0", "id": request_id, "result": {}})
        return
    if not has_id:
        # Unknown notifications do not receive a response under JSON-RPC.
        return
    if method == "initialize":
        if not isinstance(params, dict):
            _rpc_error(request_id, -32602, "Invalid initialize parameters")
            return
        requested = params.get("protocolVersion")
        selected = requested if requested in SUPPORTED_PROTOCOLS else "2025-11-25"
        _json_line({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": selected,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": "Use paired_power_calculate for paired t-test power calculations. n_total is the number of matched pairs.",
            },
        })
        return
    if method == "tools/list":
        _json_line({"jsonrpc": "2.0", "id": request_id, "result": {"tools": [_TOOL]}})
        return
    if method == "tools/call":
        result = _call_tool(params)
        _json_line({"jsonrpc": "2.0", "id": request_id, "result": result})
        return
    _rpc_error(request_id, -32601, f"Method not found: {method}")


def main() -> int:
    # stdout is reserved for newline-delimited JSON-RPC messages.
    for line in sys.stdin:
        if len(line.encode("utf-8")) > MAX_FRAME_BYTES:
            _rpc_error(None, -32600, "JSON-RPC frame exceeds the 1 MiB limit")
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            _rpc_error(None, -32700, "Parse error")
            continue
        _handle(request)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())