# Legacy scripts (archived, do not run)

These are the original shell scripts from the first commit of this repo. They are
kept for reference only. **Do not execute them.**

Why they were removed from the root:

- `agent.sh`, `api.sh` and `run_api.sh` rewrite `agent.py` / `api_server.py` via
  heredoc. Running one would silently replace the current provider-agnostic agent
  with a Gemini- or Groq-specific script, undoing the rewrite.
- `api.sh`, `run_api.sh` and `test.sh` contain a hardcoded API key fallback
  (`my-secret-wassay-key-123`). The current `api_server.py` refuses to start
  without `CUSTOM_API_KEY` instead.
- `install_skills.sh` installs browser-use and playwright system-wide and clones
  a third-party skills repo into `~/.agent/skills`. It is not needed: skills are
  plain markdown in `skills/` next to the agent.

The current equivalents:

| Old script          | What to do instead                                  |
|---------------------|-----------------------------------------------------|
| `agent.sh`          | `python3 agent.py`                                  |
| `api.sh`            | `python3 api_server.py --port 8000`                 |
| `run_api.sh`        | `python3 api_server.py --port 8000`                 |
| `install_skills.sh` | drop a `.md` file into `skills/`                    |
| `test.sh`           | `./run_tests.sh`                                    |
| `terminal.bat`      | empty file, Windows leftover                        |
