"""Verify MCP tools and the natural-language agent orchestration without an API key."""
from __future__ import annotations

import json
from pathlib import Path

import agent
from agent import McpClient


ROOT = Path(__file__).resolve().parent
VECTORS = ROOT / "public_vectors.jsonl"


def check_value(actual: object, expected: object, case_id: str, field: str) -> None:
    if isinstance(expected, int) and not isinstance(expected, bool):
        if actual != expected or isinstance(actual, bool):
            raise AssertionError(f"{case_id}.{field}: expected exact integer {expected}, got {actual!r}")
    elif not isinstance(actual, (int, float)) or isinstance(actual, bool):
        raise AssertionError(f"{case_id}.{field}: expected number {expected}, got {actual!r}")
    elif abs(actual - expected) > max(1e-6, abs(expected) * 1e-6):
        raise AssertionError(f"{case_id}.{field}: expected {expected}, got {actual}")


def verify_mcp() -> None:
    cases = [json.loads(line) for line in VECTORS.read_text(encoding="utf-8").splitlines() if line.strip()]
    with McpClient(ROOT / "mcp_server.py") as client:
        tools = client.list_tools()
        if [tool.get("name") for tool in tools] != ["paired_power_calculate"]:
            raise AssertionError("MCP server did not expose the expected calculator")
        for case in cases:
            arguments = {key: value for key, value in case["input"].items() if key != "test"}
            actual, is_error = client.call_tool("paired_power_calculate", arguments)
            if is_error:
                raise AssertionError(f"{case['id']}: MCP returned an error: {actual}")
            for field, expected in case["expected"].items():
                check_value(actual.get(field), expected, case["id"], field)

        bad, is_error = client.call_tool("paired_power_calculate", {
            "mode": "post-hoc", "tails": 1, "dz": 0.5, "alpha": 0.05, "n_total": 2,
        })
        if not is_error or bad.get("code") != "OUT_OF_RANGE":
            raise AssertionError(f"MCP range validation failed: {bad}")
        missing, is_error = client.call_tool("paired_power_calculate", {
            "mode": "post-hoc", "tails": 1, "alpha": 0.05, "n_total": 45,
        })
        if not is_error or missing.get("code") != "MISSING_PARAM":
            raise AssertionError(f"MCP required-field validation failed: {missing}")
    print(f"MCP stdio: {len(cases)}/{len(cases)} public vectors passed; boundary validation passed")


def verify_agent_loop() -> None:
    seen = {"requests": 0, "tool_result": None}

    def fake_responses_api(payload: dict) -> dict:
        seen["requests"] += 1
        if seen["requests"] == 1:
            tool = payload["tools"][0]
            parameters = tool["parameters"]
            if not tool.get("strict") or parameters.get("additionalProperties") is not False:
                raise AssertionError("OpenAI tool schema is not strict")
            if set(parameters.get("required", [])) != set(parameters["properties"]):
                raise AssertionError("Strict function schema must require every property")
            return {"output": [{
                "type": "function_call",
                "name": "paired_power_calculate",
                "call_id": "fake-call-1",
                "arguments": json.dumps({
                    "mode": "a-priori",
                    "tails": 1,
                    "dz": 0.5,
                    "alpha": 0.05,
                    "power": 0.95,
                    "n_total": None,
                    "beta_alpha_ratio": None,
                }),
            }]}
        if seen["requests"] == 2:
            output = payload["input"][-1]
            if output.get("type") != "function_call_output":
                raise AssertionError("Agent did not return MCP result to the model")
            seen["tool_result"] = json.loads(output["output"])
            if seen["tool_result"].get("n_total") != 45:
                raise AssertionError(f"Agent's MCP result has unexpected N: {seen['tool_result']}")
            return {"output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": "Gerekli örneklem büyüklüğü 45 eşleştirilmiş çifttir."}],
            }]}
        raise AssertionError("Agent made an unexpected extra model request")

    answer, tool_results = agent.run_agent(
        "Tek kuyruklu, dz 0.5, alfa 0.05, güç 0.95 için kaç çift gerekir?",
        api_request=fake_responses_api,
        server_path=ROOT / "mcp_server.py",
    )
    if "45" not in answer or len(tool_results) != 1 or seen["requests"] != 2:
        raise AssertionError("Natural-language agent loop did not complete one MCP-backed calculation")
    print("Agent loop: natural-language request -> model function call -> MCP result -> final response passed (mock API)")


def main() -> int:
    verify_mcp()
    verify_agent_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())