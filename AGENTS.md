# Agent instructions

## UI rule (mandatory)

> Before writing or changing any UI component in this project, read `DESIGN.md`
> at the root and strictly enforce Impeccable anti-slop rules.

Concretely, for any UI work:

1. Read `DESIGN.md` at the project root first. It defines the palette, type
   scale, spacing, radii, and component patterns. It is the source of truth.
2. Load the `vibe-design` skill (`skills/vibe-design.md`) and follow its
   checkpoints: anti-slop bans, the `/impeccable` review commands, Realtime
   Colors contrast standards, and the React Bits motion rules.
3. Enforce the hard bans — no default-Inter-everywhere, no purple-to-blue
   gradients, no nested cards, no gray text on colored backgrounds, no
   rounded-square icon tiles above headings.
4. Verify contrast numerically against WCAG AA (4.5:1 body, 3:1 large) before
   considering the work done.
5. At most one WebGL/background animation per page.

## Project layout

- `agent/` — the agent harness: `core.py` (loop), `tools.py`, `providers.py`,
  `skills.py` (skill loader).
- `skills/` — markdown skills with YAML frontmatter. Only `name` +
  `description` are always in context; the body loads on demand via
  `load_skill`.
- `providers/` — model provider adapters (ollama, custom, base).
- `custom-model/` — the from-scratch PyTorch model: `model.py`, `provider.py`,
  `sample_data.txt`, trained `custom_model.pth`.
- `tests/` — pytest suite. Run with `./run_tests.sh`.

## Conventions

- Python: type hints, `from __future__ import annotations`, stdlib-first.
- Never commit `.env` (gitignored). `.env.example` is the template.
- Skills are kebab-case `.md` files; see `skills/writing-skills.md`.
