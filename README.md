# HR Policy Assistant (RAG)

A retrieval-augmented generation (RAG) chatbot that answers employee questions about a company's HR policy document. Built with LangChain, Groq-hosted LLMs, Jina embeddings, and a Qdrant Cloud vector store, with input/output safety guardrails and LangSmith tracing.

## How it works

1. **Ingest** — `hr_assistant/document_loader.py` loads `data/hr_policy.txt`, and `hr_assistant/splitter.py` splits it into chunks (`CHUNK_SIZE=500`, `CHUNK_OVERLAP=60`).
2. **Embed & store** — `hr_assistant/embeddings.py` creates embeddings with Jina (`jina-embeddings-v2-base-en`), and `hr_assistant/vector_store.py` uploads/loads them from a Qdrant Cloud collection (reused on subsequent runs instead of re-embedding).
3. **Retrieve** — `hr_assistant/tools.py` wraps the vector store retriever (top-k = 3) as a `search_hr_policy` tool.
4. **Agent** — `hr_assistant/agent.py` builds a LangChain agent (`openai/gpt-oss-20b` via Groq) that calls the search tool to ground its answers.
5. **Guardrails** — `hr_assistant/guardrails.py` runs a separate Groq safety model (`openai/gpt-oss-safeguard-20b`) to screen both the incoming question (prompt injection, requests for other employees' data) and the outgoing answer (PII leaks, unauthorized promises, suspicious links) before it reaches the user.
6. **Everything is wired together** in `hr_assistant/pipeline.py` (`build_hr_assistant()` / `ask()`), used by both entry points below.

## Entry points

- `python main.py` — CLI demo that asks a few sample HR questions.
- `streamlit run app.py` — interactive chat UI.
- `rag.ipynb` — notebook version for experimentation.

## Project layout

```
hr_assistant/
  config.py          settings, env vars, system prompt
  document_loader.py load the HR policy text file
  splitter.py         chunk the document
  embeddings.py       Jina embeddings model
  vector_store.py     Qdrant Cloud build/load/retriever
  tools.py             search tool for the agent
  llm.py                Groq LLM setup
  agent.py             LangChain agent construction
  guardrails.py        input/output safety checks
  pipeline.py           wires everything together (build_hr_assistant, ask)
  logger.py             file logging (logs/)
  tracing.py             LangSmith tracing check
data/hr_policy.txt      source HR policy document
docs/                    notes on logging, LangSmith, Qdrant Cloud migration, guardrail attack testing
NOTES/                   reference PDFs
```

## Setup

1. Install [uv](https://github.com/astral-sh/uv):
   ```
   pip install uv
   ```
2. Create and activate a virtual environment:
   ```
   uv venv ragenv
   ragenv\Scripts\activate
   ```
3. Install dependencies:
   ```
   uv pip install -r requirements.txt
   ```
4. Create a `.env` file with:
   ```
   GROQ_API_KEY=...
   JINA_API_KEY=...
   QDRANT_URL=...
   QDRANT_API_KEY=...
   QDRANT_COLLECTION_NAME=hr_policy
   LANGSMITH_TRACING=false
   LANGSMITH_ENDPOINT=...
   LANGSMITH_API_KEY=...
   LANGSMITH_PROJECT=...
   ```

## Git basics

```
git add .
git commit -m "Some message"
git push
```
