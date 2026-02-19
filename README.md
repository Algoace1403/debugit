# CI/CD Healing Agent

An autonomous agent that clones a GitHub repository, detects test failures, classifies bugs, generates fixes using Claude AI, commits them to a feature branch, and monitors CI/CD — iterating up to 5 times until all tests pass. Built for the RIFT 2026 Hackathon.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              REACT DASHBOARD  (Vercel)                       │
│  ┌──────────┐┌──────────┐┌───────┐┌────────┐┌────────────┐ │
│  │  Input   ││  Run     ││ Score ││ Fixes  ││ CI/CD      │ │
│  │  Section ││  Summary ││ Panel ││ Table  ││ Timeline   │ │
│  └────┬─────┘└────▲─────┘└──▲────┘└───▲────┘└─────▲──────┘ │
│       │     Zustand Store + WebSocket  │           │        │
└───────┼───────────┼──────────┼─────────┼───────────┼────────┘
        │ POST      │ WS       │ REST    │           │
        │ /heal     │ /ws/     │ /runs/  │           │
        ▼           │          │         │           │
┌───────────────────────────────────────────────────────────────┐
│              FASTAPI BACKEND  (Railway)                        │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │             LANGGRAPH STATE MACHINE                      │  │
│  │                                                         │  │
│  │  repo_analyzer → test_runner → bug_classifier           │  │
│  │       │              ▲            │                      │  │
│  │       │              │            ▼                      │  │
│  │       │         ci_monitor ← git_ops ← fix_validator    │  │
│  │       │              │                    ▲              │  │
│  │       │              ▼                    │              │  │
│  │       │           scorer            fix_generator        │  │
│  │       │              │                                   │  │
│  │       │              ▼                                   │  │
│  │       └────────► END (results.json)                      │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│  Services: Claude API  │  GitHub API  │  Sandbox  │  Parsers  │
└───────────────────────────────────────────────────────────────┘
```

**Pipeline nodes:**

| Node | What it does |
|------|-------------|
| `repo_analyzer` | Clone repo, detect language/framework, install deps, create branch |
| `test_runner` | Run tests in sandbox, parse output (pytest/jest/vitest/mocha) |
| `bug_classifier` | Rule-based classification first, Claude LLM fallback for LOGIC bugs |
| `fix_generator` | Claude generates minimal unified diff patches |
| `fix_validator` | Apply patch → test → revert if worse |
| `git_ops` | One commit per iteration, push to feature branch (never main) |
| `ci_monitor` | Poll GitHub Actions, fall back to local tests if no CI |
| `scorer` | Calculate score: base 100 + speed bonus - efficiency penalty |

## Tech Stack

- **Backend:** Python 3.11, FastAPI, LangGraph, Anthropic SDK, httpx
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS v4, Zustand
- **AI:** Claude (Sonnet for classification, Haiku/Sonnet for fix generation)
- **Deploy:** Railway (backend) + Vercel (frontend)

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git
- A GitHub personal access token with `contents:write` and `actions:read`
- An Anthropic API key

### 1. Clone

```bash
git clone https://github.com/your-org/ci-heal-agent.git
cd ci-heal-agent
```

### 2. Backend

```bash
# Copy and fill in environment variables
cp backend/.env.example backend/.env
# Edit backend/.env with your ANTHROPIC_API_KEY and GITHUB_TOKEN

# Run (creates venv, installs deps, starts uvicorn on :8000)
bash backend/scripts/run_local.sh
```

Or manually:

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then edit .env
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Frontend

```bash
# In a separate terminal:
bash frontend/scripts/run_local.sh
```

Or manually:

```bash
cd frontend
npm install
VITE_API_URL=http://127.0.0.1:8000 npx vite --host 127.0.0.1
```

Open http://127.0.0.1:5173 in your browser.

### 4. Run Tests

```bash
# Backend (76 tests)
cd backend && source venv/bin/activate
python -m pytest tests/ -q

# Frontend (type check + build)
cd frontend && npm run build
```

## Deployment

### Backend → Railway

1. **Create a new Railway project** from the `backend/` directory.

2. **Set environment variables** on Railway:

   | Variable | Value |
   |----------|-------|
   | `ANTHROPIC_API_KEY` | `sk-ant-...` |
   | `GITHUB_TOKEN` | `ghp_...` (needs `contents:write`, `actions:read`) |
   | `DATA_DIR` | `/data/runs` |
   | `ALLOWED_ORIGINS` | `https://your-app.vercel.app` (comma-separated) |
   | `MAX_ITERATIONS` | `5` |

3. **Mount a volume** at `/data` for persistent run artifacts.

4. **Deploy.** Railway auto-detects the Dockerfile. The entrypoint uses `$PORT` automatically.

5. **Note the Railway URL** (e.g., `https://ci-heal-agent-production.up.railway.app`).

### Frontend → Vercel

1. **Import the repo** on Vercel.

2. **Set root directory** to `frontend`.

3. **Build settings:**
   - Build command: `npm run build`
   - Output directory: `dist`

4. **Set environment variables:**

   | Variable | Value |
   |----------|-------|
   | `VITE_API_URL` | `https://<railway-domain>` |

   The WebSocket URL is derived automatically (`https://` → `wss://`).

5. **Deploy.** Vercel auto-builds on push.

## End-to-End Test

1. Start backend + frontend locally (see Local Development above).

2. Open http://127.0.0.1:5173

3. Fill in the form:
   - **Repository URL:** Any public repo with failing tests, e.g., `https://github.com/your-org/broken-test-repo`
   - **Team Name:** `RIFT ORGANISERS`
   - **Leader Name:** `Saiyam Kumar`

4. Click **"Run Agent"**.

5. Watch the dashboard:
   - **Progress Stepper** shows which pipeline node is active.
   - **Run Summary Card** appears when the first iteration completes.
   - **Fixes Applied Table** lists each bug fix with type, file, line, and status.
   - **CI/CD Timeline** shows each iteration's pass/fail and links to GitHub Actions.
   - **Score Breakdown** shows final score when done.

6. On GitHub, check that a branch named `RIFT_ORGANISERS_SAIYAM_KUMAR_AI_Fix` was created with `[AI-AGENT]` prefixed commits.

### GitHub Token Permissions

The `GITHUB_TOKEN` must have:
- **`contents:write`** — to push commits to the feature branch
- **`actions:read`** — to poll GitHub Actions workflow status

For public repos, a fine-grained token scoped to those repos is sufficient.

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/heal` | Start healing. Body: `{repo_url, team_name, leader_name}` |
| `GET` | `/api/v1/runs/{run_id}` | Run status + results |
| `GET` | `/api/v1/runs/{run_id}/results` | Download results.json |
| `GET` | `/api/v1/runs` | List all runs |
| `GET` | `/api/v1/health` | Health check |
| `WS` | `/ws/{run_id}` | Real-time pipeline events |

### Example: Start a healing run

```bash
curl -X POST http://127.0.0.1:8000/api/v1/heal \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/org/repo","team_name":"RIFT ORGANISERS","leader_name":"Saiyam Kumar"}'
```

Response:
```json
{"run_id": "abc-123", "status": "running"}
```

## Security

- **GitHub token is never sent from the frontend.** The `POST /heal` body contains only `repo_url`, `team_name`, and `leader_name`.
- **Token is read from environment variables only** (`os.environ["GITHUB_TOKEN"]` on the backend).
- **Token is redacted** before persisting state to disk or broadcasting via WebSocket.
- **Token is not stored** in `results.json` or any log output.
- **CORS is restricted** to configured origins in production (not `*`).

## Branch Naming Convention

Branches follow the format: `{TEAM_NAME}_{LEADER_NAME}_AI_Fix`

- Team name and leader name are uppercased
- Spaces/hyphens become underscores
- Special characters are stripped
- Suffix is the literal `_AI_Fix` (mixed case)

Example: Team `"RIFT ORGANISERS"` + Leader `"Saiyam Kumar"` → `RIFT_ORGANISERS_SAIYAM_KUMAR_AI_Fix`

## Project Structure

```
ci-heal-agent/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + CORS
│   │   ├── config.py            # Pydantic settings
│   │   ├── api/
│   │   │   ├── routes.py        # REST endpoints
│   │   │   └── websocket.py     # WS connection manager
│   │   ├── agents/
│   │   │   ├── graph.py         # LangGraph state machine
│   │   │   ├── orchestrator.py  # Pipeline runner
│   │   │   ├── callbacks.py     # WS event broadcaster
│   │   │   └── nodes/           # 8 pipeline nodes
│   │   ├── models/
│   │   │   ├── schemas.py       # Pydantic models
│   │   │   └── state.py         # LangGraph state TypedDict
│   │   ├── services/
│   │   │   ├── claude_service.py
│   │   │   ├── github_service.py
│   │   │   ├── sandbox.py
│   │   │   ├── parsers.py
│   │   │   ├── scoring.py
│   │   │   ├── run_store.py
│   │   │   └── results_builder.py
│   │   └── utils/
│   │       ├── framework_detector.py
│   │       └── logger.py
│   ├── tests/                   # 76 tests
│   ├── scripts/run_local.sh
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── types/index.ts
│   │   ├── stores/useHealStore.ts
│   │   ├── hooks/useWebSocket.ts
│   │   ├── lib/api.ts
│   │   └── components/
│   │       ├── Layout.tsx
│   │       ├── InputSection.tsx
│   │       ├── ProgressStepper.tsx
│   │       ├── RunSummaryCard.tsx
│   │       ├── ScoreBreakdownPanel.tsx
│   │       ├── FixesAppliedTable.tsx
│   │       └── CICDTimeline.tsx
│   ├── scripts/run_local.sh
│   ├── vite.config.ts
│   ├── package.json
│   └── index.html
│
└── README.md
```
