# 01. Logger

**Branch:** `logging` (built on top of `main`)

## What is a logger?

A logger is a way for your program to write down, step by step, what it is
doing while it runs — instead of (or in addition to) `print()` statements.
Every line it writes is called a "log". Think of it like a flight recorder
("black box") for your app: if something goes wrong, or you just want to
know what happened during a run, you open the log file and read the story
of that run.

## Why do we need it instead of just using `print()`?

- `print()` only shows up in your terminal, and disappears once the terminal
  closes. Logs are saved to a file, so you can look at them later — even
  days later.
- `print()` gives you no context automatically. A logger can automatically
  attach the time, the severity (how serious the message is), and which
  file/module it came from.
- You can turn logging up or down (e.g. "only show me errors") without
  touching your code, because of **log levels** (below).
- In a real product, you often have many things running (a web app, a
  background job, an agent). Logs are how you debug "what actually
  happened" after the fact, e.g. why a user got a wrong answer, or why a
  request was slow.

## Log levels — from least to most serious

Python's built-in `logging` module (which we use here) has 5 standard
levels. You pick the right one for each message:

| Level      | Method            | When to use it |
|------------|-------------------|-----------------|
| `DEBUG`    | `logger.debug()`  | Very detailed info, only useful while actively debugging (e.g. "raw response from API was ..."). Usually turned off in normal runs. |
| `INFO`     | `logger.info()`   | Normal, expected events — "the app started", "loaded 5 chunks", "user asked X". This is what we use in this branch. |
| `WARNING`  | `logger.warning()`| Something unexpected happened, but the app can keep going (e.g. "retrying after a slow API call"). |
| `ERROR`    | `logger.error()`  | Something failed — a request crashed, a function couldn't complete. The app might still be running, but this specific thing broke. |
| `CRITICAL` | `logger.critical()`| The whole app is in serious trouble and might not be able to continue at all. |

We set our logger's level to `INFO` in this branch
(`hr_assistant/logger.py`), which means `INFO`, `WARNING`, `ERROR`, and
`CRITICAL` messages all get logged, but `DEBUG` messages are hidden. You
can change the level to `DEBUG` later if you want maximum detail while
troubleshooting.

## How it works in this codebase

- `hr_assistant/logger.py` is a new "Step 0" module. It:
  1. Creates a `logs/` folder automatically if it doesn't already exist.
  2. Picks one log file per run, named with the time the run started
     (e.g. `logs/run_20260801_143210.log`).
  3. Exposes one function, `get_logger(name)`, that every other file calls.
- Every module now does this at the top:
  ```python
  from hr_assistant.logger import get_logger
  logger = get_logger(__name__)
  ```
  `__name__` is the module's own name (e.g. `hr_assistant.tools`), so when
  you read the log file you can see exactly which file logged which
  message.
- Then, at the important steps in each function, we call
  `logger.info(...)` to record what happened (e.g. "Loaded 1 document(s)",
  "search_hr_policy called with query: ...", "Final answer: ...").

## Files changed

| File | What changed |
|------|--------------|
| `hr_assistant/logger.py` | **New file.** Sets up the shared logger and the `logs/` folder. |
| `hr_assistant/document_loader.py` | Logs which file is loaded and how many documents were loaded. |
| `hr_assistant/splitter.py` | Logs how many chunks the document was split into. |
| `hr_assistant/embeddings.py` | Logs which embedding model is being initialized. |
| `hr_assistant/vector_store.py` | Logs build vs. load-from-disk path, save confirmation, retriever creation. |
| `hr_assistant/tools.py` | Logs every search query sent to `search_hr_policy` and how many chunks matched. |
| `hr_assistant/llm.py` | Logs which LLM model is initialized. |
| `hr_assistant/agent.py` | Logs agent creation. |
| `hr_assistant/pipeline.py` | Logs the start/end of building the assistant, and every question + final answer. |
| `main.py` | Logs the start and end of a CLI run. |
| `app.py` | Logs when a new question comes in through the Streamlit chat. |
| `.gitignore` | Added `logs/` so log files (generated per run) are never committed. |

## Verified working

Ran `python main.py` on this branch: the app answered all 3 demo
questions correctly (same output as the `main` baseline), and a new file
appeared under `logs/` containing a full step-by-step trace of the run —
from "Vector store already exists on disk, reusing it" through each
`search_hr_policy` call to the final answers.

## Assignment for students

Right now, all runs write into a single flat `logs/` folder — one file
per run, e.g. `logs/run_20260801_143210.log`. Your task: change
`hr_assistant/logger.py` so that logs are organized **date-wise**, with
**run-wise** files inside each date folder. For example:

```
logs/
  2026-08-01/
    run_143210.log
    run_181530.log
  2026-08-02/
    run_091205.log
```

Hints:
- You'll need two `datetime.now()` formats: one for the folder name
  (just the date) and one for the file name (just the time).
- Don't forget to create the date folder with `os.makedirs(..., exist_ok=True)`
  the same way we create the top-level `logs/` folder today.
