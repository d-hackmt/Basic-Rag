# 06. Evaluations (LangSmith Datasets + Experiments)

**Branch:** `evaluations` (built on top of `portkey-gateway`)

## Tracing vs. evaluation - what's the difference?

We already have LangSmith **tracing** (from the `langsmith-tracing`
branch) - it records what happened during a run, after the fact.

**Evaluation** is different: you give it a fixed set of question +
reference-answer pairs (a **Dataset**), run the agent against every one
of them, and have a second LLM **judge** each answer. The result is an
**Experiment** - a scored, repeatable snapshot you can compare against
future experiments after changing a prompt, model, or guardrail, to see
if quality actually went up or down.

```
10 questions (Dataset: "hr-policy-qa")
      |
      v
target(): the real agent answers each one
      |
      v
judge LLM (@hrpolicy, different model) scores each answer:
   - correctness   (matches the reference answer?)
   - groundedness   (supported by the retrieved chunks?)
      |
      v
Experiment results, uploaded to LangSmith
```

## What we check: correctness + groundedness (nothing else, on purpose)

Two evaluators, both "LLM-as-judge" (a second LLM reads the answer and
scores it), from the `openevals` package:

- **Correctness** - does the answer match the reference answer?
- **Groundedness** (also called **faithfulness** in other eval
  frameworks like RAGAS - same metric, different name) - is every claim
  in the answer actually supported by the chunks that were retrieved,
  or did the model add something not present in the context?

These catch different failure modes. Correctness alone would have
missed the real bug we found (see "What we found" below) - the core
fact was right, so correctness passed it, but groundedness caught an
extra claim that wasn't in the retrieved policy text at all.

We deliberately did **not** add conciseness, trajectory (tool-call)
checking, or anything else - see the Assignment section for those as
follow-ups.

Cost, token usage, and latency are **not** evaluators we wrote - they're
captured automatically by LangSmith for every run, visible in the
Experiment view without any extra code.

## The judge model

Both evaluators use the same judge LLM, routed through Portkey on the
same slug as the main app (`@hrpolicy` - see `docs/05_portkey_gateway.md`
for why there's only one slug in use) but a **different underlying
model**, so it isn't grading its own output verbatim.

## The 10 test cases

One question per section of `data/hr_policy.txt`, so the whole document
is covered:

| # | Question | Reference answer |
|---|----------|-------------------|
| 1 | How many days of paid annual leave do I get per year? | 20 days |
| 2 | How many days of unused annual leave can be carried forward? | Up to 5 days |
| 3 | How many paid sick days do I get per year? | 10 days |
| 4 | How many days per week can I work from home? | Up to 2 days, with manager approval |
| 5 | How long is the probation period? | 3 months |
| 6 | What is the notice period during probation? | 15 days |
| 7 | What is the standard notice period for resignation? | 30 days |
| 8 | Within how many days must reimbursement claims be submitted? | 30 days of the expense |
| 9 | How many public holidays does the company observe each year? | 12 |
| 10 | Within how many days is full and final settlement processed after the last working day? | 45 days |

## Files changed

| File | What changed |
|------|--------------|
| `hr_assistant/evaluation.py` | **New file.** The 10 test cases, `_ensure_dataset()` (creates the LangSmith dataset once, reuses it after), `target()` (runs the real agent + captures retrieved context), the correctness and groundedness evaluators, and `run_evaluation()`. |
| `evaluate.py` | **New file** (repo root, mirrors `main.py`). `python evaluate.py` runs the whole thing. |
| `requirements.txt` | Added `openevals`. |

Nothing in `pipeline.py`, `tools.py`, or `agent.py` changed -
`evaluation.py` builds its own retriever directly from
`vector_store.py` (to capture context for groundedness) rather than
modifying the app's own request path.

## A real bug along the way: an invalid LangSmith API key

Mid-testing, `evaluate.py` appeared to succeed (printed "Done", real
agent calls happened) but nothing showed up on the LangSmith dashboard.
Root cause, confirmed by direct API calls: `client.evaluate()` creates
the dataset and the experiment "shell" synchronously first, then
uploads the actual per-example results in the background - so if the
API key becomes invalid partway through (which is what happened here),
you get a dataset and an empty experiment (0 runs) with no error
surfaced locally. Fixed by getting a valid key. Also caught a second,
separate bug in our own verification scripts: calling `Client()`
directly without first importing `hr_assistant.config` (which is what
actually calls `load_dotenv()`) silently uses whatever stale
`LANGSMITH_API_KEY` happens to be in the raw shell environment, not the
one in `.env` - easy to mistake for a real credential problem.

## Verified working

Ran `python evaluate.py` for real, then independently confirmed via the
LangSmith API (not just trusting the printed "Done"):
- 120 traced runs (every internal step - retriever calls, LLM calls,
  tool calls - across all 10 test cases) and 20 feedback entries (10
  correctness + 10 groundedness) actually landed.
- **Correctness: 10/10 passed.**
- **Groundedness: 9/10 passed.**

### What we found: a real hallucination correctness missed

Question: *"How many paid sick days do I get per year?"*

Answer: *"...you're entitled to 10 paid sick days per calendar year. **If
you need more time off due to illness, just submit a request through
the HR portal** and provide a medical certificate if you're away for
more than two consecutive days."*

The core fact (10 days) is correct, so **correctness passed this**. But
the retrieved context never mentions being able to request *additional*
sick leave beyond the 10 days - the agent invented a plausible-sounding
process that isn't in the policy. **Groundedness correctly caught it**,
scoring it false with the reasoning: "this is an unsupported suggestion
that extends beyond the information given." This is exactly the kind of
subtle, confident-sounding hallucination that a reference-answer-only
check can't catch, and confirms groundedness was worth adding, not just
a theoretical nice-to-have.

## Assignment for students

1. Look at the actual failing example in your LangSmith dashboard
   (Datasets & Experiments -> hr-policy-qa -> the latest experiment) -
   find the sick-leave row and read the judge's full reasoning.
2. Add a **conciseness** evaluator (`openevals.prompts.CONCISENESS_PROMPT`,
   same `create_llm_as_judge` pattern) and see how the agent's fairly
   chatty answers score.
3. Try adding an 11th test case for something *not* in
   `data/hr_policy.txt` at all (e.g. "What's the maternity leave
   policy?") with no reference answer, and see whether groundedness
   still passes it (it should, if the agent correctly says "I don't
   know" and adds nothing).
4. (Harder) Look at the `agentevals` package for trajectory evaluation -
   check that the agent actually called `search_hr_policy` for every
   question, rather than answering from its own knowledge.
