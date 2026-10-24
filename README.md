# paired-power

A clean-room, pure-Python paired-sample t-test power calculator. The CLI, MCP server, and natural-language agent are thin interfaces over the same paired_power.py calculation engine.

## Requirements

Python 3.10 or newer. The CLI and local MCP server use only the Python standard library and make no network requests. The optional natural-language agent sends the user's prompt and calculator tool results to the OpenAI Responses API; this requires an API key and may incur API usage charges.

## CLI

From this directory:

~~~powershell
python --version
python gpower_clone.py --test t-paired --mode a-priori --tails 1 --dz 0.5 --alpha 0.05 --power 0.95
python gpower_clone.py --test t-paired --mode post-hoc --tails 2 --dz 0.5 --alpha 0.05 --n_total 45
python gpower_clone.py --test t-paired --mode compromise --tails 1 --dz 0.5 --beta_alpha_ratio 1 --n_total 45
python gpower_clone.py --version
~~~

On Windows, gpower-clone.cmd forwards arguments to the CLI.

## MCP server

The server uses MCP stdio with newline-delimited JSON-RPC. An MCP host launches it as a child process; keep stdout reserved for protocol messages. For example, add this server entry to the host's MCP configuration and replace the path with the full path to this folder:

~~~json
{
  "mcpServers": {
    "paired-power": {
      "command": "python",
      "args": ["C:\\path\\to\\outputs\\mcp_server.py"]
    }
  }
}
~~~

The server exposes one read-only tool, paired_power_calculate, for all five modes. It uses the CLI's validation and calls the shared calculation engine. On Windows, mcp-server.cmd is a convenience launcher.

## Natural-language agent

The agent discovers the local MCP tool, passes its schema to the OpenAI Responses API as a strict function, calls the MCP server with the model's arguments, then returns the calculation result to the model for a natural-language answer. It never fills in missing statistical inputs.

In PowerShell, set a key in the current terminal session and run a request:

~~~powershell
$env:OPENAI_API_KEY = "your-api-key"
python agent.py "Tek kuyruklu, dz 0.5, alfa 0.05, güç 0.95 için kaç eşleştirilmiş çift gerekir?"
~~~

Optionally set OPENAI_MODEL; the default is gpt-6-astra. Keep the API key out of the repository and do not paste it into chat. The key is read from the environment and is not saved by the program. On Windows, paired-power-agent.cmd forwards arguments to the agent.

## Reproducible checks

~~~powershell
python verify_public_vectors.py
python verify_integrations.py
~~~

The first command checks the five instructor-provided public vectors through the CLI. The second checks the MCP handshake, tool discovery and calls, input errors, and the agent's model-to-MCP orchestration with a mocked API response. It does not call OpenAI. The hidden-vector exact-N gate cannot be measured without the instructor's hidden vectors.

## Evidence and scope

- SPEC.md is the clean-room writer's implementation brief.
- REA_EVIDENCE.md records [REA] evidence separately from supplementary [UI OBSERVATION] screenshots in evidence/screenshots/.
- VALIDATION.md records public and integration checks and states what remains unverified.
- No G*Power executable or decompiler output is included. The engine is independently implemented from statistical definitions and observed behavior for this educational, non-commercial course exercise; this project is not G*Power and is not endorsed by its authors.