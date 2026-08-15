# 05. Portkey Gateway (LLM Routing + Fallback)

**Branch:** `portkey-gateway` (built on top of `qdrant-cloud`)

## What is an LLM gateway?

Until now, `llm.py` called Groq directly:

```python
ChatGroq(model="openai/gpt-oss-20b", ...)
```

That means our raw `GROQ_API_KEY` lives in `.env`, and if Groq has an
outage or rate-limits us, the app just breaks - there's nothing to fall
back to.

A gateway sits between our app and the LLM provider:

```
Before:  Our app  ->  Groq directly
After:   Our app  ->  Portkey  ->  Groq (via a stored "@slug" credential)
```

Portkey stores the real Groq API key behind a short name (a **slug**,
set up once in the Portkey dashboard). Our code never sees that raw
key - it only holds a `PORTKEY_API_KEY`, and tells Portkey which slug
to use. If that slug/model fails, Portkey can automatically retry
against a second one, without our code knowing anything went wrong:

```
                          [1] try primary
Our app  --->  Portkey  --------------------->  @rag  (Groq)
                  |
                  |  [2] if @rag fails, try fallback
                  '--------------------------->  @rag1  (Groq)
```

## What we implemented: slug routing + fallback (kept minimal on purpose)

We looked at a reference notebook covering 10 gateway features
(observability metadata, retries, timeouts, fallback, load balancing,
caching, saved dashboard configs, full production setup). We're only
implementing **two** of them here, on purpose:

1. **Slug routing** - the main LLM call goes through Portkey instead of
   straight to Groq.
2. **Fallback** - if the primary target fails, Portkey automatically
   tries a second one.

Everything else (retries, timeouts, metadata tagging, load balancing)
is real and available on the free tier, but adds more moving parts than
this lesson needs - see the Assignment section.

## Why caching was tried and left out

We attempted request caching (both `mode: "simple"` and
`mode: "semantic"`, several config shapes, matching a reference
notebook's approach exactly) and verified via the actual
`x-portkey-cache-status` response header - not just by eyeballing
latency, which is how the reference notebook "confirmed" it (and on
closer inspection, the notebook's own two calls used different
reworded questions with different answers, which isn't good evidence of
a real cache hit either).

Every attempt came back `MISS`, including on a byte-identical repeated
request. Portkey's docs already say semantic caching needs an
Enterprise plan; simple caching is documented as free-tier, but it
didn't engage either. This looks like an account/workspace-level
setting that needs enabling in the Portkey dashboard, not a code
problem on our side - left out of this branch rather than shipping
something we couldn't verify. See the Assignment section.

## How fallback was verified (not just "it returned an answer")

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

`config.targets[1]` confirms the second target actually served the
request after the first one failed - genuine fallback, not a lucky
success.

## Files changed

| File | What changed |
|------|--------------|
| `hr_assistant/gateway.py` | **New file.** `get_gateway_llm()` - builds a `ChatOpenAI` pointed at Portkey's gateway URL, with a `GATEWAY_CONFIG` (fallback: primary `@rag` -> fallback `@rag1`) passed via `createHeaders()`. |
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
"replace the main LLM call." Routing the guard model through Portkey
too is a natural next step (see Assignment).

## Verified working

1. **Tool calling through the gateway** - bound a test tool to a
   gateway-routed `ChatOpenAI` and confirmed it returned a real
   `tool_call`, before touching `llm.py` at all. This is what makes the
   swap safe: the agent's tool-calling behavior is unaffected.
2. **Full app, end-to-end** - ran `main.py` on this branch: all 3
   baseline questions answered correctly, confirmed via the log line
   `Routing LLM calls through Portkey (primary=@rag, fallback=@rag1)`
   that requests were actually going through Portkey, not silently
   falling back to a direct Groq call.
3. **Fallback, for real** - see the section above; confirmed via
   `x-portkey-last-used-option-index: config.targets[1]` that the
   fallback target genuinely served the request after the primary
   failed.

## Assignment for students

1. Check your Portkey dashboard for a cache-related setting and see if
   turning it on gets `x-portkey-cache-status` to return `HIT` on a
   repeated identical question. If you find it, add
   `"cache": {"mode": "simple"}` to `GATEWAY_CONFIG` in `gateway.py` and
   re-verify with the header check shown above (don't just trust the
   latency).
2. Add automatic retries: `{"retry": {"attempts": 3, "on_status_codes": [429, 500, 502, 503, 504]}}`
   merged into `GATEWAY_CONFIG`. Test it against the same "bogus model
   name" trick used above, but with `on_status_codes` covering whatever
   status that failure returns.
3. Route the guard model (`guardrails.py`) through Portkey too, using a
   third slug. Bonus: give it its own metadata tag
   (`portkey.with_options(metadata={"feature": "guardrail"})`) so its
   usage shows up separately from the main LLM's in the Portkey
   dashboard.
