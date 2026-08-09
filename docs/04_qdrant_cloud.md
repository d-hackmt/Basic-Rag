# 04. Qdrant Cloud (Vector Store)

**Branch:** `qdrant-cloud` (built on top of `prompt-guard`)

## What changed, in plain words

Until now, when the app "built a vector store," it did this:
1. Split the HR policy document into chunks
2. Turned each chunk into a vector (a list of numbers) using Jina embeddings
3. Saved those vectors into a file on your own computer, inside
   `data/faiss_index/`, using FAISS (a local vector search library)

From now on, step 3 is different: instead of saving to a local file, we
upload the vectors to a **collection** on Qdrant Cloud - a vector
database that runs on someone else's server, reachable over the
internet.

```
BEFORE:  chunks -> embeddings -> data/faiss_index/   (your laptop only)

AFTER:   chunks -> embeddings -> Qdrant Cloud "hr_policy" collection
                                  (internet, reachable by anyone with the
                                   URL + API key, survives your machine)
```

## Why move from local to cloud?

A local FAISS file works fine for one person running the app on one
laptop. It starts to fall over once you leave that laptop:

- **Every fresh clone rebuilds from scratch.** `data/faiss_index/` isn't
  committed to git (it's a binary blob, not source code), so anyone who
  clones the repo has to re-embed the whole document before they can ask
  a single question. A cloud vector DB is already there, waiting -
  everyone connects to the same collection.
- **No sharing.** If two people (or a real deployed app with many users)
  need to search the same knowledge base, a local file can only be read
  by the process that has it on disk. A cloud database can serve many
  clients at once.
- **Doesn't scale past "demo."** FAISS-on-a-laptop is fine for our 9
  tiny chunks. A real HR knowledge base with thousands of documents
  needs a database built for that - indexing, filtering, and search at
  scale, without you managing any of it yourself.
- **Survives your machine.** A crashed laptop or a wiped `data/` folder
  used to mean rebuilding the index. Now the data lives on Qdrant's
  servers, independent of your machine.

The trade-off: it's now a networked dependency. If the cluster is down
or unreachable, the app can't retrieve anything - see the "known issue"
note at the bottom.

## Files changed

| File | What changed |
|------|--------------|
| `hr_assistant/vector_store.py` | Every function rewritten to use `langchain_qdrant.QdrantVectorStore` instead of `langchain_community.vectorstores.FAISS`. `build_vector_store()` now uploads straight to a Qdrant Cloud collection. `load_vector_store()` connects to an existing collection instead of reading a local file. `vector_store_exists()` asks the Qdrant Cloud cluster whether the collection exists, instead of checking for a file on disk. `save_vector_store()` is **gone** - there's no separate "save" step anymore, `build_vector_store()` already uploads directly. |
| `hr_assistant/pipeline.py` | `build_vector_store_for_document()` no longer calls `save_vector_store()`; print/log messages updated to talk about "Qdrant Cloud collection" instead of "saved vector store on disk". |
| `hr_assistant/config.py` | Removed the local `VECTOR_STORE_PATH`. Added `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION_NAME` (defaults to `"hr_policy"`). `check_api_keys()` now also fails fast with a clear message if the Qdrant env vars are missing. |
| `.env` / `.env.example` | Added the three `QDRANT_*` variables, same pattern as the LangSmith keys. |
| `requirements.txt` | Removed `faiss-cpu`. Added `langchain-qdrant` and `qdrant-client`. |
| `.gitignore` | Removed the now-unused `data/faiss_index` line. |

Nothing in `tools.py`, `agent.py`, or the rest of `pipeline.py` changed
at all - they only ever talk to a "retriever" object, and
`get_retriever()`'s signature didn't change. That's the benefit of
keeping the vector store behind its own small module: swapping the
storage technology underneath didn't ripple anywhere else.

## Verified working

The cluster we first tested against was unreachable (every request,
even a plain `GET /` with no auth, returned a generic `404 page not
found` - consistent with a paused free-tier cluster; confirmed it
wasn't a code/DNS issue via direct `curl`). Once an active cluster URL
+ API key were in `.env`, re-ran the full check:

1. First run: console showed "No Qdrant Cloud collection found,
   building one from scratch...", and all 3 baseline questions
   returned their correct answers.
2. Inspected the collection directly with `qdrant_client` - `hr_policy`
   exists with **9 points** (one per chunk) and 768-dimension vectors
   (matches Jina's embedding size).
3. Second run: console showed "Found an existing Qdrant Cloud
   collection, connecting to it" instead of rebuilding - confirmed via
   the log line and an `httpx` GET to `/collections/hr_policy/exists`
   returning `200 OK`.

## Assignment for students

1. Once your cluster is verified working, open the Qdrant Cloud
   dashboard and look at the `hr_policy` collection - inspect a couple
   of points and see the vector + the original chunk text stored
   alongside it (the `page_content` field).
2. Try changing `QDRANT_COLLECTION_NAME` in `.env` to a new name and
   rerun - confirm the app builds a brand new collection instead of
   reusing the old one, since `vector_store_exists()` checks by name.
3. (Optional) Portkey (used in the next branch) can also proxy and log
   Qdrant requests, not just LLM calls - see
   [Portkey's Qdrant integration docs](https://portkey.ai/docs/integrations/vector-databases/qdrant).
   We didn't wire this up here to keep this branch minimal, but it's
   worth exploring once both `qdrant-cloud` and `portkey-gateway` are in
   place.
