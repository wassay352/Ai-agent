---
name: vibe-design
description: Use when writing, reviewing, or modifying any UI component, page, or style.
---

# Vibe design — UI/UX review checkpoints

Before writing or changing ANY UI component in this project, read `DESIGN.md`
at the project root and enforce the rules below. `DESIGN.md` is the source of
truth for palette, spacing, typography, and component shape; this skill is the
review discipline that keeps generated UI from looking machine-made.

## 0. Always read DESIGN.md first

`DESIGN.md` at the project root defines the design system (colors, type scale,
spacing, radii, component patterns). Read it before touching UI. If a rule here
conflicts with `DESIGN.md`, `DESIGN.md` wins — it is the project's own system.

## 1. Anti-AI-slop rules (hard bans)

Reject these on sight. They are the tells of generated UI:

- **No default Inter everywhere.** Use the type stack `DESIGN.md` specifies.
  Inter as a fallback is fine; Inter as the whole personality is not.
- **No purple-to-blue gradients.** The single most common generated-UI cliché.
- **No nested cards.** A card inside a card inside a card is visual noise.
  One surface level per concept.
- **No gray text on colored backgrounds.** Contrast fails and it reads as
  disabled. Use a tint of the background's own hue, or white/black.
- **No rounded-square icon tiles above headings.** The "icon in a rounded box,
  then a title, then a paragraph" triplet is a template, not a design.

## 2. Review commands

Run the matching pass for the task at hand:

| Command | Use when |
|---|---|
| `/impeccable critique` | Reviewing a finished screen for design quality |
| `/impeccable audit` | Checking accessibility, contrast, semantics |
| `/impeccable polish` | Final pass before shipping — spacing, alignment, states |
| `/impeccable layout` | Fixing structure, hierarchy, responsive behavior |
| `/impeccable colorize` | Reworking palette, contrast, color roles |
| `/impeccable typeset` | Fixing type scale, line-height, measure, weights |

## 3. Realtime Colors discipline

Every screen must have an explicit 5-role palette, wired as CSS variables and
mirrored in Tailwind classes:

- **Text** — primary reading color
- **Background** — page canvas
- **Primary** — main action / brand
- **Secondary** — supporting surface or accent
- **Accent** — the one thing that draws the eye

Contrast must meet **AA minimum** (4.5:1 body text, 3:1 large text). Target
AAA (7:1) for body copy where the palette allows. Never ship unverified
contrast — compute it, don't eyeball it.

## 4. React Bits for motion

When the task calls for interactive motion, hero backgrounds, or UI effects,
use React Bits components rather than hand-rolling:

- Text: `SplitText`, `BlurText`
- Backgrounds: `Aurora`
- Cards: `SpotlightCard`, `MagicBento`

Install the TS + Tailwind variant matching this stack:

```bash
npx shadcn@latest add @react-bits/[ComponentName]-TS-TW
```

**Performance limit: at most ONE WebGL/background animation per page.** More
than one tanks frame rate and looks chaotic.

## Pitfalls

- Skipping the `DESIGN.md` read is the most common failure — it leads to
  inventing a palette that fights the project's own system.
- `!important` text overrides break light mode. Fix the token, not the symptom.
- Verify contrast numerically. "Looks fine" on a bright monitor is not AA.
