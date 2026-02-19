# Demo Guide — CI/CD Healing Agent (RIFT 2026)

## Test Repository Recommendation

Use a small Python repo with 2-3 intentional bugs. Create one at:
https://github.com/new

**Name:** `broken-test-repo`

Add these files:

### `src/__init__.py` (empty)
### `tests/__init__.py` (empty)

### `src/utils.py`
```python
import os  # unused import (LINTING bug)

def add(a, b):
    return a - b  # LOGIC bug: should be a + b

def greet(name):
    return "Hello " + nme  # NameError bug: typo 'nme' instead of 'name'
```

### `tests/test_utils.py`
```python
from src.utils import add, greet

def test_add():
    assert add(2, 3) == 5

def test_greet():
    assert greet("World") == "Hello World"
```

Push and you're ready.

---

## 2-Minute Demo Script

### Before demo (30 sec setup)
1. Have backend + frontend running locally
2. Open http://127.0.0.1:5173 in browser
3. Have GitHub repo tab open showing the broken code

### Demo flow (90 seconds)

**[0:00] Open dashboard**
> "This is our CI/CD Healing Agent. It autonomously detects, fixes, and validates broken code."

**[0:10] Fill form + click Run Agent**
- Repo URL: `https://github.com/YOUR_USERNAME/broken-test-repo`
- Team: `RIFT ORGANISERS`
- Leader: `Saiyam Kumar`

> "I paste the repo URL, team name, and leader name. The agent takes over from here."

**[0:20] Watch Pipeline Progress**
> "The pipeline clones the repo, runs tests, and finds 2-3 failures."

**[0:35] Point at classifications appearing**
> "It classifies each bug — NameError as an IMPORT issue, the wrong operator as LOGIC. Rule-based classification is instant; only LOGIC bugs go to Claude AI."

**[0:45] Watch fixes being applied**
> "For each bug, Claude generates a minimal unified diff patch. The agent applies it, re-runs tests, and only keeps fixes that make tests pass."

**[0:55] Show commit + CI**
> "All working fixes are committed in one commit per iteration with a clear [AI-AGENT] prefix, pushed to a branch named RIFT_ORGANISERS_SAIYAM_KUMAR_AI_Fix."

**[1:10] Show final results**
> "The dashboard shows: all failures detected, fixes applied, final score of 110 — 100 base plus 10 speed bonus for finishing under 5 minutes."

**[1:20] Switch to GitHub**
> "On GitHub, you can see the branch with the AI-generated commit. The code is actually fixed."

**[1:30] Architecture highlight**
> "The backend uses LangGraph for the state machine, FastAPI for real-time WebSocket updates, and Claude for AI-powered fix generation. Frontend is React + Tailwind. Zero human intervention."

---

## Key Points for LinkedIn / Judges

### What makes it special
1. **Truly autonomous** — no human in the loop after clicking "Run"
2. **Rule-first, AI-second** — rule-based classification catches 70%+ of bugs instantly, Claude only handles LOGIC errors (saves cost + time)
3. **Safe by design** — never pushes to main, validates every fix before committing, reverts bad patches
4. **Real-time dashboard** — WebSocket-driven progress updates, judges see every step live
5. **Production-ready architecture** — LangGraph state machine, disk-backed persistence, Docker sandbox

### Architecture highlights to emphasize
- **8-node LangGraph pipeline** with conditional retry loop
- **Rule-first classification** (parsers.py handles SyntaxError, ImportError, TypeError, IndentationError patterns)
- **Patch validation** — applies diff, runs full test suite, reverts if worse
- **One commit per iteration** — keeps commit count under penalty threshold
- **Token security** — GitHub token never leaves backend, redacted from all outputs

### Numbers that impress
- 77 automated tests covering every node
- Under 3 minutes for typical broken repos
- Score: 110/110 for fast repos (100 base + 10 speed bonus)
- Max 5 iterations, typically fixes in 1-2
