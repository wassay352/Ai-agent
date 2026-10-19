---
name: python-debugging
description: Use when Python code errors, tests fail, or behaviour is unexpected.
---

# Python debugging

Work from evidence, not guesses.

1. Reproduce the failure with the smallest possible command and capture the
   full traceback. Do not summarise it — read the last frame.
2. Identify which line actually raised. The traceback's final frame is the
   cause; earlier frames are the call path.
3. Check the obvious first: wrong interpreter or venv, missing dependency,
   stale `__pycache__`, wrong working directory.
4. Form one hypothesis, then test it with a single command. Do not change
   several things at once — you will not know which one fixed it.
5. After two failed attempts at the same fix, stop and ask the user for the
   exact error text rather than looping.

Never suppress an exception with a bare `except: pass` to make a test go green.
