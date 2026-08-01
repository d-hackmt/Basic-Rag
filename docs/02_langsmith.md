# 02. LangSmith Tracing

**Branch:** `langsmith-tracing` (built on top of `logging`)

## What is LangSmith?

LangSmith is LangChain's observability platform. Where our own
`logger.py` (see [01_logger.md](01_logger.md)) writes plain-text lines
to a file on your machine, LangSmith captures a structured, visual
**trace** of everything that happened inside a single `agent.invoke(...)`
call, and uploads it to a dashboard on smith.langchain.com.

A trace shows you, as a tree:
- Every step the agent took (LLM call → tool call → LLM call → final answer)
- The exact prompt sent to the LLM, and the exact response it got back
- How many tokens were used and roughly what it cost
- How long each step took (latency), so you can see where time went
- If a step failed, the exact error

## Logging vs. tracing — why do we want both?

| | `logger.py` (our own logs) | LangSmith tracing |
|---|---|---|
| Where it lives | `logs/` folder on your machine, plain text | smith.langchain.com, a web dashboard |
| What it shows | The events *we chose* to log (a handful of `logger.info()` calls) | Every LLM/tool call automatically, with full inputs/outputs, tokens, latency |
| Best for | Quick "what happened in this run" trail, works offline, free | Debugging *why* the agent answered the way it did, comparing runs, spotting slow or expensive calls, sharing a trace link with a teammate |

They're complementary: our logs tell a short story of the run; LangSmith
gives you the full, clickable detail of every LLM interaction inside it.

## How it works (no code changes needed for tracing itself!)

LangChain has built-in support for LangSmith. If these four environment
variables are set, **every** `agent.invoke(...)` / LLM call in the app is
automatically traced — we don't have to add any tracing code around our
LLM calls ourselves:

```
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=<your key>
LANGSMITH_PROJECT="hrrag"
```

- `LANGSMITH_TRACING=true` — turns tracing on. Set it to `false` (or
  remove it) to turn tracing off with zero code changes.
- `LANGSMITH_ENDPOINT` — which LangSmith server to send traces to (the
  default cloud one, unless you're self-hosting).
- `LANGSMITH_API_KEY` — your personal/team key, found in LangSmith under
  Settings → API Keys. **Never commit this to git.**
- `LANGSMITH_PROJECT` — groups all traces from this app together under
  one project name ("hrrag") in the dashboard, so they don't mix with
  traces from other projects in your account.

Because `config.py` already calls `load_dotenv()`, putting these in
`.env` is enough for LangChain to pick them up.

## What we added on top of "just set the env vars"

Setting the env vars is enough to *get* tracing. But for this class we
also want it to be **visible** that tracing is on, without having to go
check LangSmith every time. So we added a small `tracing.py` module that
logs (via our own logger from the previous branch) one line at the start
of every run: `LangSmith tracing ENABLED - project 'hrrag', ...` or
`LangSmith tracing is OFF`.

## Files changed

| File | What changed |
|------|--------------|
| `.env` | **Added** (not committed - gitignored) `LANGSMITH_TRACING`, `LANGSMITH_ENDPOINT`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`. |
| `.env.example` | **New file.** Same variable names as `.env`, with blank/placeholder values, so anyone cloning the repo knows what to fill in. Safe to commit. |
| `hr_assistant/config.py` | Reads the four `LANGSMITH_*` variables (mirrors the existing `GROQ_API_KEY` / `JINA_API_KEY` pattern). |
| `hr_assistant/tracing.py` | **New file.** `check_langsmith_tracing()` logs whether tracing is on/off for this run. Doesn't turn tracing on itself - the env vars do that. |
| `hr_assistant/pipeline.py` | Calls `check_langsmith_tracing()` once, at the start of `build_hr_assistant()`. |
| `requirements.txt` | Added `langsmith` explicitly under a new "langsmith tracing" section (it was already installed as a dependency of `langchain-core`, but we list it directly since it's a tool we're actively using/teaching). |

## Verified working

Ran `python main.py` on this branch with `LANGSMITH_TRACING=true` in
`.env`: the app answered all 3 demo questions exactly as before, the
run log showed `LangSmith tracing ENABLED - project 'hrrag'`, and the
run appeared as a new trace under the **hrrag** project on
smith.langchain.com, showing each LLM call and the `search_hr_policy`
tool call inside it.

## Assignment for students

1. Open your `hrrag` project on smith.langchain.com and find the trace
   for a run you just did. Click into it and find:
   - The exact prompt (including the system prompt) sent to the LLM
   - How many tokens the run used in total
   - How long the `search_hr_policy` tool call took vs. the LLM calls
2. Try setting `LANGSMITH_TRACING=false` in `.env`, rerun `main.py`, and
   confirm two things: the app still works fine, and no new trace shows
   up in LangSmith. This proves tracing is fully optional and doesn't
   affect the app's behavior - only its observability.
3. (Optional, harder) LangSmith lets you add custom metadata/tags to a
   trace (e.g. `agent.invoke(..., config={"tags": ["demo"]})`). Try
   tagging each question in `main.py` with the question's topic (e.g.
   "leave", "wfh", "notice-period") and find those tags in the
   LangSmith UI.
