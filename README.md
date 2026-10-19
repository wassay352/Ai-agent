# Ai-agent

A personal AI agent that runs on your own machine. It can run shell commands,
read and write files, and follow skills you teach it in plain markdown.

Provider-agnostic: one line in `.env` switches between a fully local model
(Ollama), Groq, or OpenRouter.

## Quick start

```bash
cd Ai-agent-main

# 1. Configure
cp .env.example .env
#    Default is Ollama (local, private, no API key).
#    To use a cloud provider instead, set PROVIDER=groq and add GROQ_API_KEY.

# 2. Start Ollama and pull a model (skip if using a cloud provider)
ollama serve &
ollama pull qwen2.5-coder:1.5b

# 3. Verify connectivity
python3 agent.py --check

# 4. Run
python3 agent.py
```

No pip installs are required — the agent uses only the Python standard library.

## Usage

```
python3 agent.py                      # interactive chat
python3 agent.py --provider groq      # override the provider
python3 agent.py --model llama3.2:3b  # override the model
python3 agent.py --read-only          # block all file writes
python3 agent.py --workspace ~/proj   # run against another directory
python3 agent.py --check              # test provider connectivity, exit
python3 agent.py --quiet              # hide tool-call traces
```

Inside the REPL: `exit` or `quit` to leave, `/clear` to reset conversation
history.

## Providers

| PROVIDER     | Needs a key          | Default model                 | Notes                     |
|--------------|----------------------|-------------------------------|---------------------------|
| `ollama`     | no                   | `qwen2.5-coder:1.5b`          | Local, private, offline   |
| `groq`       | `GROQ_API_KEY`       | `llama-3.3-70b-versatile`     | Fast, generous free tier  |
| `openrouter` | `OPENROUTER_API_KEY` | `anthropic/claude-3.5-sonnet` | Many models, one key      |

Set `MODEL=` in `.env` to override the default for whichever provider is active.

Note: a 7B model needs roughly 5–6 GB of RAM. On a machine with less, use
`MODEL=qwen2.5-coder:1.5b` (the default here) or `llama3.2:3b`.

## Teaching it (this is the "training")

There is no fine-tuning here. You teach the agent by writing **skills** —
markdown files in `skills/` with a short frontmatter header:

```markdown
---
name: deploy-checklist
description: Use when deploying the app to production.
---

# Deploy checklist

1. Run the test suite: `python3 tests/test_agent.py`
2. Check `git status` is clean.
3. Tag the release: `git tag -a v1.0 -m "release"`
```

How it works: only the `name` and `description` of every skill go into the
system prompt, so the index stays cheap. When your request matches a
description, the agent calls `load_skill` to pull in the full body and follows
it. This means you can keep dozens of skills without wasting context.

To add a skill, drop a new `.md` file in `skills/` and restart the agent. No
code changes needed.

Two starter skills are included: `git-workflow` and `python-debugging`.

## What the agent can do

| Tool         | Purpose                                                  |
|--------------|----------------------------------------------------------|
| `run_shell`  | Run bash in the workspace (destructive commands blocked) |
| `read_file`  | Read a text file, returns numbered lines                 |
| `write_file` | Create or overwrite a file in the workspace              |
| `list_dir`   | List a directory                                         |
| `load_skill` | Pull in the full text of a skill (only if skills exist)  |

## Serving it as an API

`api_server.py` exposes the same provider layer over an OpenAI-compatible
endpoint, so other apps or an OpenAI SDK client can call your model. It uses
only the standard library — no FastAPI needed.

```bash
# Generate a key and add it to .env as CUSTOM_API_KEY=...
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

python3 api_server.py --port 8000
```

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $CUSTOM_API_KEY" \
  -d '{"messages":[{"role":"user","content":"hello"}]}'
```

The server refuses to start if `CUSTOM_API_KEY` is unset — there is no
hardcoded fallback. `GET /health` is open; everything else requires the bearer
token.

## Safety model

The original version of this project gave the model an unguarded
`subprocess.run(shell=True)`. That is remote code execution by design. This
version keeps the capability but adds two guard rails:

- **Command deny-list** — `rm -rf`, `mkfs`, `dd of=/dev/*`, fork bombs,
  `curl | sh`, `git push --force`, `git reset --hard`, `shutdown` and similar
  are refused before they run, and the model is told why.
- **Workspace jail** — file tools resolve paths and refuse anything outside the
  workspace root. Writes to `.git/`, `.env`, `.ssh/`, `id_rsa*`, `.aws/` and
  credentials files are blocked.

Run with `--read-only` to disable writes entirely.

These are guard rails against mistakes, not a sandbox. A determined model can
still do damage through `run_shell`. Run the agent in a directory you are
willing to lose, or in a container.

## Layout

```
agent.py            entry point / CLI
api_server.py       OpenAI-compatible HTTP endpoint
agent/
  core.py           the agent loop (model -> tool -> result -> model)
  providers.py      Ollama / Groq / OpenRouter behind one interface
  tools.py          shell + file tools and the safety policy
  skills.py         skill loader and system-prompt index
skills/             your skills live here (markdown)
tests/
  test_agent.py     tools, providers, skills (offline)
  test_loop.py      agent loop with a scripted fake provider (offline)
run_tests.sh        runs both suites
.env.example        config template
```

## Tests

```bash
./run_tests.sh
```

17 tests across two suites, all offline — no network, no API keys, no model
needed.

- `test_agent.py` (9) — provider registry and key enforcement, the command
  deny-list, the workspace jail, protected paths, file round-trips, read-only
  mode, skill parsing.
- `test_loop.py` (8) — the real agent loop driven by a scripted fake provider:
  tool dispatch, tool-result feedback, refusal handling, unknown tools,
  malformed JSON arguments, skill loading, and the infinite-loop guard.
