# research-assistant

A research assistant [Managed Deep Agent](https://docs.langchain.com/langsmith/python/managed-deep-agents-overview) built with `[managed-deepagents](https://github.com/langchain-ai/managed-deepagents)` `0.7.3`.

It searches the web with Tavily, reads the pages it finds, searches scholarly papers through OpenAlex, answers with citations, and keeps shared durable notes. Routing that must not be optional is enforced in middleware rather than left to the prompt — see [Enforced routing](#enforced-routing). It runs a DeepInfra chat model through the OpenAI-compatible API. Managed Deep Agents is in public beta and currently runs on **US LangSmith Cloud** only.

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
  memory.py                # opt-in durable memory (shared by every caller)
  middleware/skill_gate.py # enforces skill loading, evidence, and real URLs
  tools/search.py          # Tavily internet_search
  tools/fetch.py           # Tavily fetch_page — read a source, not a snippet
  tools/papers.py          # OpenAlex scholarly paper search
  tools/context7.py        # Context7 library documentation lookup
  tools/_tavily.py         # shared lazily-initialized Tavily client
  skills/qa/               # clarifying-question skill
  skills/research/         # outline → search → notes → cited brief
  skills/deep-research/    # rigorous multi-source investigations
  skills/citation-hygiene/ # source selection and claim-to-citation checks
  skills/daily-recap/      # progress and activity summaries
  skills/response-formatting/ # response structure and presentation
  evals/cited-research/    # Harbor task (not deployed)
  evals/harbor-job.json    # Harbor job config from `mda evals init`
```

`memory.py` mounts one Context Hub tree at `/memories/agent/` for **all** callers of the deployment and preserves it across redeployments of that same deployment. It is not shared between separately named deployments and is removed if the deployment is deleted. Do not store personal data, customer records, or credentials there. MCP connectors (`connectors/mcp.py`) are not supported. Restart `mda dev` after adding or changing `memory.py` — it is discovered at compile time, not by hot reload.

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

`mda dev` requires `uv` on `PATH`. It resolves the local LangGraph development server itself, so you do not need a global `langgraph` CLI. Restart `mda dev` after adding or changing `memory.py` — it is discovered at compile time, not by hot reload.

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

For signed-in end users with private threads, switch to Supabase identity (`auth.supabase(...)`). Durable memory (`memory.py`) is still shared by every caller of the deployment even with Supabase identity.

## Skills and tools


| Piece             | Role                                                           |
| ----------------- | -------------------------------------------------------------- |
| `internet_search` | Tavily web search — ranked snippets (`TAVILY_API_KEY`)         |
| `fetch_page`      | Tavily extract — the readable text of a page (`TAVILY_API_KEY`) |
| `paper_search`    | OpenAlex scholarly paper search (optional contact email)        |
| `context7_docs`   | Focused library/framework documentation (`CONTEXT7_API_KEY`)   |
| `skills/qa`       | Ask up to three clarifying questions when the request is vague |
| `skills/research` | Outline, search web and scholarly papers, note-take, cited brief |
| `skills/deep-research` | Decompose, triangulate, and synthesize complex investigations |
| `skills/citation-hygiene` | Match claims with authoritative sources and citations |
| `skills/daily-recap` | Summarize progress, decisions, open items, and next actions |
| `skills/response-formatting` | Choose clear structure, formatting, and citation placement |


### Enforced routing

Skills use progressive disclosure: the model sees each skill's name and
description and is trusted to `read_file` the matching `SKILL.md`. That is a
suggestion, so a fast model complies only some of the time — the same reason a
rule in `instructions.md` gets skipped.

`middleware/skill_gate.py` turns the suggestion into a checked precondition. It
runs inside `wrap_model_call`, so it inspects a draft answer **before** that
answer reaches graph state and re-asks the model when something is missing:

| Requirement | Checked against |
| ----------- | --------------- |
| The workflow for this request class was loaded | a `read_file` of the skill's `SKILL.md` in the current turn |
| Something was actually looked up | a call to `internet_search`, `paper_search`, `context7_docs`, or `fetch_page` in the current turn |
| Every URL in the answer is real | the URL appears in a tool result from the current turn |

Request classes and the skills they require are `SKILL_RULES` in `agent.py`,
evaluated in order, first match wins. Greetings, questions about the
conversation, and pure text transformations are ungated. Corrections are
appended to the model *request* only, so the thread the user sees carries no
retry scaffolding and a rejected draft is never shown. After `max_retries` the
last draft is returned rather than failing the turn — the gate is a bounded
nudge, not a hard block.

Managed Deep Agents does not expose LangGraph nodes or edges: `define_deep_agent`
returns a spec that the managed runtime compiles. `middleware` is the supported
hook, and authored middleware is spliced in after the deepagents base stack
(skills, filesystem, subagents) and before the managed tail.

`mda deploy` syncs `instructions.md` and `skills/**` to Context Hub. You can edit them in the LangSmith UI without a full code redeploy; a later deploy overwrites deploy-owned context from this repo.

## Evaluate

Managed Deep Agent evals are [Harbor](https://www.harborframework.com/docs/tasks) evals. Tasks are direct children of `evals/` (this project includes `evals/cited-research/`). `evals/` is not included in the deployed build.

Initialize the Harbor workspace once (writes `evals/harbor-job.json` if missing):

```bash
uv run mda evals init
```

Harbor does **not** read `.env` unless you pass it. In the shell that runs Harbor, export at least:

```bash
export DEEPINFRA_API_KEY DEEPINFRA_MODEL TAVILY_API_KEY LANGSMITH_API_KEY
```

Or use `--env-file .env`. Then run (adjust dataset name if you like):

```bash
HARBOR_LANGSMITH_DATASET=mda-research-assistant-evals \
PYTHONPATH=.mda/evals/harbor-adapter \
uv run --env-file .env --python 3.12 --with 'harbor[langsmith]==0.21.0' harbor run \
  --config evals/harbor-job.json --yes \
  --plugin mda_harbor.job_plugin:MDAJobPlugin \
  --plugin mda_harbor.langsmith_plugin:LangSmithPlugin
```

`cited-research` checks that the agent writes `/app/answer.txt` with web and scholarly-paper citations. Docker is required for Harbor’s default environment.

View the results after a run:

```bash
uv run --python 3.12 \
  --with 'harbor[langsmith]==0.21.0' \
  harbor view .mda/evals/jobs
```

To inspect one specific run, pass its job directory instead:

```bash
uv run --python 3.12 \
  --with 'harbor[langsmith]==0.21.0' \
  harbor view .mda/evals/jobs/2026-09-20__20-04-43
```

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

This removes the deployment, the tracing project created with it, and the Context Hub repo for this agent's context and memory. It asks first; pass `--yes` to skip the prompt. Agent memory and thread history are not recoverable afterwards.

## Environment

Copy `.env.example` to `.env`. `mda deploy` loads `.env` and forwards non-reserved keys as deployment secrets. A value exported only in your shell is not enough for those secrets — put them in `.env` or as LangSmith workspace secrets.


| Variable                                    | Used for                                                                                       |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `LANGSMITH_API_KEY`                         | Deploy, logs, delete, and caller auth (`identity.py`)                                          |
| `LANGSMITH_WORKSPACE_ID`                    | Required when the API key needs an explicit workspace (`mda deploy --workspace-id` also works) |
| `LANGSMITH_PROJECT`, `LANGSMITH_TRACING`, … | Local / hosted tracing                                                                         |
| `DEEPINFRA_API_KEY`, `DEEPINFRA_MODEL`      | Chat model in `agent.py`                                                                       |
| `TAVILY_API_KEY`                            | `internet_search`, `fetch_page`                                                                |
| `CONTEXT7_API_KEY`                          | `context7_docs`                                                                                |
| `OPENALEX_EMAIL`                            | Optional polite-pool contact for `paper_search`                                                |
| `LANGFUSE_*`, `OTEL_*`                      | Optional OpenTelemetry export to Langfuse                                                      |


Reserved LangSmith keys authenticate the CLI and are not uploaded as user-managed secrets. Do not commit `.env`.
