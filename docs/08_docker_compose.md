# 08. Docker Compose

**Branch:** `docker-compose` (built on top of `docker`)

## The problem Compose solves

The `docker` branch showed you `docker run` with a handful of flags:
`-d`, `--name`, `-p`, `--env-file`. That's manageable for one container.
This app actually needs **two** things running: the Streamlit web app,
and (on demand) the evaluation pipeline. Juggling two full `docker run`
commands by hand, remembering every flag each time, doesn't scale.

**Docker Compose** replaces that with one file (`docker-compose.yml`)
that describes every service - its image, its command, its ports, its
env vars - and one command to bring any of them up.

## Microservices, in one shared image

We're deliberately using the **same image** for both services here, not
two separate Dockerfiles - because `app` and `eval` need the exact same
dependencies (`evaluate.py` imports from `hr_assistant`, same as
`app.py` does). Splitting into two Dockerfiles would just be duplicated
content with no real difference. What actually makes them separate
services isn't the image - it's that they have different **lifecycles**:

- `app` is a **service** - long-running, always up, serves traffic.
- `eval` is a **job** - runs once, does its work, exits.

That distinction is real microservices thinking (independently
deployable, independently scaled units), even sharing one image. This
is also the standard real-world pattern for closely related services
(think "web" + "worker" in a typical production setup).

## `docker-compose.yml`, explained

```yaml
services:
  app:
    build: .
    command: streamlit run app.py --server.address=0.0.0.0
    ports:
      - "8501:8501"
    env_file:
      - .env

  eval:
    build: .
    command: python evaluate.py
    env_file:
      - .env
    profiles:
      - tools
```

- `build: .` (both services) - build from the same `Dockerfile` in this
  folder. Compose builds it once per service the first time, then
  reuses the image.
- `command:` - overrides the Dockerfile's `CMD` per service. Same
  image, different thing runs.
- `env_file: .env` - Compose loads your `.env` automatically. Unlike
  plain `docker run --env-file` (see `docs/07_docker.md`'s gotcha about
  strict formatting), Compose handled our `.env`'s looser format
  (spaces around `=`, quoted values) without any changes needed -
  verified by running `docker compose config` and confirming every
  variable resolved correctly.
- `profiles: ["tools"]` on `eval` - keeps it **out** of `docker compose
  up` by default. It only starts when you explicitly run it (see below).
  Confirmed: after `docker compose up -d app`, `docker compose ps`
  showed only `app` running - `eval` correctly stayed off.

## Commands - basics

| Command | What it does | Example |
|---|---|---|
| `docker compose up` | Build (if needed) and start every service *without* a profile, in the foreground. | `docker compose up` |
| `docker compose up -d` | Same, but in the background. | `docker compose up -d app` |
| `docker compose ps` | List this project's running containers. | `docker compose ps` |
| `docker compose ps -a` | List all of this project's containers, including stopped ones. | `docker compose ps -a` |
| `docker compose logs -f` | Stream logs from every running service live. | `docker compose logs -f` |
| `docker compose logs -f <service>` | Stream logs from just one service. | `docker compose logs -f app` |
| `docker compose build` | Rebuild the image(s) - use after changing the Dockerfile or code. | `docker compose build` |

## Commands - stopping and cleaning up (terminate everything)

| Command | What it does | Example |
|---|---|---|
| `docker compose down` | Stop and remove every container *and* the network Compose created for this project. | `docker compose down` |
| `docker compose stop` | Stop containers but leave them in place (faster to restart later). | `docker compose stop` |
| `docker compose rm -f` | Remove stopped containers without stopping first. | `docker compose rm -f` |
| `docker rmi <project>-app <project>-eval` | Remove the images Compose built (the project name defaults to the folder name). | `docker rmi basicrag-app basicrag-eval` |

`docker compose down` is the one you want almost every time - it's the
clean, complete teardown.

## Commands - advanced

| Command | What it does | Example |
|---|---|---|
| `docker compose run <service>` | Start a service as a **one-off** container - runs, and you see its exit. This is how you trigger `eval` on demand, bypassing its `profiles` restriction. | `docker compose run eval` |
| `docker compose run --rm <service> <override cmd>` | Same, but also removes the container after it exits, and lets you override the command for that one run. | `docker compose run --rm eval python -c "print('hi')"` |
| `docker compose exec <service> bash` | Open a shell inside an *already-running* service's container. | `docker compose exec app bash` |
| `docker compose config` | Print the fully-resolved config (env vars included) - useful for checking your `.env` loaded correctly. **Careful:** this prints real secret values to your terminal - don't screenshot or paste it anywhere. | `docker compose config` |

## Verified working

1. `docker compose up -d app` - built the image, started the container,
   confirmed via `curl http://localhost:8501/_stcore/health` -> `200`.
2. `docker compose ps` (no `-a`) showed only `app` - `eval` correctly
   stayed hidden behind its profile.
3. `docker compose run --rm eval` with an overridden command - imported
   `hr_assistant.evaluation` for real inside a fresh container and
   printed the dataset name and test case count, confirming the eval
   service's environment and dependencies are correct - **without**
   triggering a real `client.evaluate()` run (that costs LLM/LangSmith
   calls, left for you to trigger deliberately with `docker compose run
   eval` when you're ready to spend that budget).
4. `docker compose down` - confirmed full teardown (container, network)
   afterward.

## Files changed

| File | What changed |
|------|--------------|
| `docker-compose.yml` | **New file.** Two services sharing one image: `app` (always up) and `eval` (on-demand job, hidden behind a profile). |

## Assignment for students

1. Add a named volume to `app` so `logs/` survives container restarts
   and rebuilds, instead of starting empty every time:
   ```yaml
   volumes:
     - ./logs:/app/logs
   ```
2. Add a `healthcheck:` to `app` using the `_stcore/health` endpoint,
   and watch `docker compose ps` show a `healthy` status once it's up.
3. Actually trigger the real evaluation: `docker compose run eval`
   (no override), and open your LangSmith project to see the new
   experiment - this one does spend real API budget, do it once
   deliberately.
