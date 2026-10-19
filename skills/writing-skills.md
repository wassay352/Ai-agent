---
name: writing-skills
description: Use when the user asks you to learn a new procedure or create a skill.
---

# Writing a new skill

When the user teaches you a procedure, capture it as a skill so it survives
across sessions.

1. Choose a short kebab-case name, e.g. `docker-deploys`.
2. Create `skills/<name>.md` with frontmatter:

   ```markdown
   ---
   name: docker-deploys
   description: Use when building or deploying Docker images.
   ---
   ```

3. The `description` is the trigger. Write it as "Use when <situation>" so
   future-you knows exactly when to load it. It is the only part always in
   context, so make it specific and short.
4. Write the body as numbered steps with the exact commands to run. Include
   the pitfalls the user hit — those are the valuable part.
5. Do not restate general knowledge. A skill is for what is specific to this
   user's setup and preferences.
6. Tell the user the skill is saved and that it takes effect on restart.
