# research-assistant

A research assistant [Managed Deep Agent](https://docs.langchain.com/langsmith/python/managed-deep-agents-overview) built with `[managed-deepagents](https://github.com/langchain-ai/managed-deepagents)` `0.7.3`.

It searches the web with Tavily, answers with citations, and runs a DeepInfra chat model through the OpenAI-compatible API. Managed Deep Agents is in public beta and currently runs on **US LangSmith Cloud** only.

The agent id and default deployment name is `research-assistant-preview` (`define_deep_agent(name=...)` in `agent.py`). Override the LangSmith deployment name with `mda deploy --name` if needed.

## Prerequisites

- Python **3.12.3** (pinned in `pyproject.toml`)
- `[uv](https://docs.astral.sh/uv/)` on `PATH`
- A LangSmith workspace with Managed Deep Agents access
- API keys listed in [Environment](#environment)



## Project structure

```text
research-assistant/
  agent.py                 # define_deep_agent(...) — required `name` is the deploy id
  instructions.md          # always-loaded system prompt (synced to Context Hub on deploy)
  pyproject.toml           # Python 3.12.3 + dependencies
  uv.lock                  # locked install
  .env                     # secrets; never commit
  .env.example             # placeholder names for required keys
  identity.py              # who may call the deployment (LangSmith API key)
  tools/search.py          # Tavily internet_search
  tools/customer.py        # lookup_customer demo tool
  skills/qa/               # clarifying-question skill
```

There is no `sandbox/` directory, so MDA does not provision a LangSmith sandbox. There is no `memory.py`, so nothing is kept between runs. MCP connectors (`connectors/mcp.py`) are not supported.

## Install

```bash
cp .env.example .env   # then fill in real keys
uv sync
```



## Develop

Edit `agent.py` to change the model, tools, or middleware, and edit `instructions.md` for always-on behavior. Skills under `skills/` load on demand.

Run the compiled app on the local LangGraph development server (opens LangSmith Studio):

```bash
uv run mda dev
```

By default the server is reachable only from this machine. To bind every interface on port 2024 without opening a browser:

```bash
uv run mda dev --hostname 0.0.0.0 --port 2024 --no-browser
```

To expose the same local server over a public HTTPS URL, use a [Cloudflare Quick Tunnel](#cloudflare-quick-tunnel) instead of binding `0.0.0.0`.

`mda dev` requires `uv` on `PATH`. It resolves the local LangGraph development server itself, so you do not need a global `langgraph` CLI. Restart `mda dev` after adding a managed file such as `memory.py` or `sandbox/` — those are discovered at compile time, not by hot reload.

### Cloudflare Quick Tunnel

Quick Tunnels give a temporary `https://<random-name>.trycloudflare.com` URL for local `mda dev`. They are for development and testing: the hostname changes whenever you restart `cloudflared`.

1. Install `cloudflared` (Debian/Ubuntu) from [Cloudflare’s apt repo](https://pkg.cloudflare.com/):

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null

echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" \
  | sudo tee /etc/apt/sources.list.d/cloudflared.list

sudo apt-get update && sudo apt-get install cloudflared
cloudflared --version
```

1. Start the agent on loopback (keep this terminal open):

```bash
uv run mda dev --hostname 127.0.0.1 --port 2024 --no-browser
```

1. In another terminal, start the tunnel:

```bash
cloudflared tunnel --url http://127.0.0.1:2024
```

Use the printed HTTPS URL when connecting from another machine or through LangSmith Studio.

## Identity

`identity.py` authenticates callers with a LangSmith workspace API key (`x-api-key`). That answers whether a caller is allowed; it does **not** give each person private threads. Anyone holding the key can reach the deployment.

For signed-in end users with private threads, switch to Supabase identity (`auth.supabase(...)`). Durable memory is a separate opt-in (`memory.py`) and is shared by every caller of the deployment.

## Skills and tools


| Piece             | Role                                                           |
| ----------------- | -------------------------------------------------------------- |
| `internet_search` | Tavily web search (`TAVILY_API_KEY`)                           |
| `lookup_customer` | Demo CRM lookup                                                |
| `skills/qa`       | Ask up to three clarifying questions when the request is vague |


`mda deploy` syncs `instructions.md` and `skills/**` to Context Hub. You can edit them in the LangSmith UI without a full code redeploy; a later deploy overwrites deploy-owned context from this repo.

## Evaluate

Managed Deep Agent evals are [Harbor](https://www.harborframework.com/docs/tasks) evals. Author complete tasks under `evals/tasks/<task>/`. To start from a minimal task:

```bash
mda evals init my-task
```

That writes an optional scaffold under `evals/scaffold/my-task/`. Compile, then run the printed `harbor run` command:

```bash
mda evals compile .                    # all tasks
mda evals compile . --task my-task     # only my-task
```

`evals/` is not included in the deployed build. Harbor does not read `.env`; export the keys in the shell that runs Harbor.

## Deploy

```bash
mda deploy
```

This copies project files, generates a managed entry module, and writes a deployable build (including `langgraph.json`) to `.mda/build`. The CLI uploads that build to LangSmith.

Common options:

```bash
mda deploy --name research-assistant-dev --deployment-type dev
mda deploy --workspace-id "$LANGSMITH_WORKSPACE_ID"
mda deploy --no-wait
```

Deploy prints the Agent Server URL and the LangSmith dashboard URL. `--no-wait` exits before the deployment is fully live and skips schedule reconciliation.

## Logs

```bash
mda logs
mda logs --lines 200 --level error
```

In a terminal this streams until you press Ctrl-C. When output is piped or redirected it prints the most recent lines (1000 by default) and exits.

## Delete

```bash
mda delete
```

This removes the deployment, the tracing project created with it, the Context Hub repo for this agent's context and memory, and any managed sandboxes it created. It asks first; pass `--yes` to skip the prompt. Agent memory and thread history are not recoverable afterwards.

## Environment

Copy `.env.example` to `.env`. `mda deploy` loads `.env` and forwards non-reserved keys as deployment secrets. A value exported only in your shell is not enough for those secrets — put them in `.env` or as LangSmith workspace secrets.


| Variable                                    | Used for                                                                                       |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `LANGSMITH_API_KEY`                         | Deploy, logs, delete, and caller auth (`identity.py`)                                          |
| `LANGSMITH_WORKSPACE_ID`                    | Required when the API key needs an explicit workspace (`mda deploy --workspace-id` also works) |
| `LANGSMITH_PROJECT`, `LANGSMITH_TRACING`, … | Local / hosted tracing                                                                         |
| `DEEPINFRA_API_KEY`, `DEEPINFRA_MODEL`      | Chat model in `agent.py`                                                                       |
| `TAVILY_API_KEY`                            | `internet_search`                                                                              |
| `LANGFUSE_*`, `OTEL_*`                      | Optional OpenTelemetry export to Langfuse                                                      |


Reserved LangSmith keys authenticate the CLI and are not uploaded as user-managed secrets. Do not commit `.env`.