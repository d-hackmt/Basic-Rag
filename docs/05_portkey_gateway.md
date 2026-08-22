# 05. Portkey Gateway (LLM Routing)

**Branch:** `portkey-gateway` (built on top of `qdrant-cloud`)

## What is an LLM gateway?

Until now, `llm.py` called Groq directly:

```python
ChatGroq(model="openai/gpt-oss-20b", ...)
```

That means our raw `GROQ_API_KEY` lives in `.env`. A gateway sits
between our app and the LLM provider instead:

```
Before:  Our app  ->  Groq directly
After:   Our app  ->  Portkey  ->  Groq (via a stored "@hrpolicy" credential)
```

Portkey stores the real Groq API key behind a short name (a **slug**,
set up once in the Portkey dashboard, called `@hrpolicy` here). Our code
never sees that raw key - it only holds a `PORTKEY_API_KEY`, and tells
Portkey which slug to use.

## Why there's no fallback in this version

We originally implemented this with a **fallback**: send Portkey a
config ("try `@hrpolicy` first, if that fails try `@hrpolicy-backup`") via the
`x-portkey-config` header, and verified it worked for real (see
"Retired: how fallback was verified" below).

Some Portkey workspaces have a setting called **`block_inline_config`**
that rejects *any* config sent that way - fallback or not - with an
error: `inline_config_blocked`. That's a workspace-level setting, not a
code bug, and it doesn't show up until you hit a workspace that has it
turned on.

The fix: skip the config mechanism entirely and route straight to one
provider with `provider="@hrpolicy"` instead of `config=...`. That header
isn't validated the same way, so it works everywhere. The trade-off: no
automatic fallback to a second slug if `@hrpolicy` fails.

```
Our app  --->  Portkey  --->  @hrpolicy  (Groq)
```

If your Portkey workspace *doesn't* have `block_inline_config` on, you
can add a second slug and bring fallback back - see the Assignment.

## Why caching was tried and left out

Unrelated to the fallback issue above - we also attempted request
caching (both `mode: "simple"` and `mode: "semantic"`, several config
shapes, matching a reference notebook's approach exactly) and verified
via the actual `x-portkey-cache-status` response header, not just by
eyeballing latency like the reference notebook did.

Every attempt came back `MISS`, including on a byte-identical repeated
request. Portkey's docs say semantic caching needs an Enterprise plan;
simple caching is documented as free-tier, but it didn't engage either.
Looked like an account/workspace-level setting, not a code problem -
left out rather than shipping something we couldn't verify. See the
Assignment.

## Retired: how fallback was verified

Kept for reference - this is how we proved fallback genuinely worked,
back when this branch still used it.

A naive test (pointing the primary target at a slug that doesn't exist)
just gets rejected immediately with a 400 "Following keys are not
valid" error - Portkey validates the config before it even tries a
request, so that never actually exercises the fallback path.

To trigger a *real* runtime fallback, we pointed the primary target at
a valid slug but a **nonexistent model name** (`this-model-does-not-exist-on-groq`)
so the failure happens after Portkey accepts the config, when Groq
itself rejects the request. Then checked the response headers:

```
Answer: OK
Used provider: groq
Option index used: config.targets[1]   <- the fallback target, not the primary
```

`config.targets[1]` confirmed the second target actually served the
request after the first one failed - genuine fallback, not a lucky
success. If you bring fallback back (Assignment #1), re-verify it the
same way - don't just trust that it returned an answer.

## Files changed

| File | What changed |
|------|--------------|
| `hr_assistant/gateway.py` | `get_gateway_llm()` - builds a `ChatOpenAI` pointed at Portkey's gateway URL, routed through the single `@hrpolicy` slug via `provider=` (no config, no fallback - see above). |
| `hr_assistant/llm.py` | `get_llm()` body now just calls `get_gateway_llm()` instead of building `ChatGroq` directly. One line changed. |
| `hr_assistant/config.py` | Added `PORTKEY_API_KEY`; `check_api_keys()` now also fails fast if it's missing. `GROQ_API_KEY` is still used too - see note below. |
| `.env` / `.env.example` | Added `PORTKEY_API_KEY`. |
| `requirements.txt` | Added `portkey-ai`, `langchain-openai`. |

Nothing in `agent.py`, `tools.py`, `pipeline.py`, or `guardrails.py`
changed. `get_gateway_llm()` returns a real `langchain_openai.ChatOpenAI`,
which supports `.bind_tools()` and `.invoke()` exactly like `ChatGroq`
did - confirmed this specifically (see Verified working below) before
wiring it in, since `create_agent()` depends on tool-calling working.

**Note:** `GROQ_API_KEY` is still in `.env` and still used directly -
`guardrails.py`'s guard model (`openai/gpt-oss-safeguard-20b`) is not
routed through the gateway in this branch, to keep the change scoped to
"replace the main LLM call."

## Verified working

1. **Tool calling through the gateway** - bound a test tool to a
   gateway-routed `ChatOpenAI` and confirmed it returned a real
   `tool_call`, before touching `llm.py` at all. This is what makes the
   swap safe: the agent's tool-calling behavior is unaffected.
2. **Full app, end-to-end** - ran `main.py` on this branch: all 3
   baseline questions answered correctly, confirmed via the log line
   `Routing LLM calls through Portkey (provider=@hrpolicy)` that requests
   were actually going through Portkey, not silently falling back to a
   direct Groq call.

## Assignment for students

1. If your Portkey workspace allows inline configs (check by trying to
   add a `config=` with a `strategy: fallback` block - if it works
   without an `inline_config_blocked` error, you're clear), bring real
   fallback back using `@hrpolicy-backup` (already set up in the
   dashboard, just not wired into the code yet) as the second target,
   verified the same way as the retired section above (don't just trust
   "it returned an answer").
2. Add automatic retries via a config, once you've confirmed your
   workspace allows configs: `{"retry": {"attempts": 3, "on_status_codes": [429, 500, 502, 503, 504]}}`.
3. Route the guard model (`guardrails.py`) through Portkey too, using
   the same `@hrpolicy` slug but a different model name, the same way
   `get_gateway_llm()` does it for the main LLM.
