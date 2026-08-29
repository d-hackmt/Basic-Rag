# 07. Docker Basics

**Branch:** `docker` (built on top of `evaluations`)

## Why Docker, before we go to the cloud?

Right now, running this app requires: the right Python version, `uv` (or
`pip`) installed, every package in `requirements.txt` installed
correctly, and your `.env` file in place. That's "works on my machine" -
if a teammate's Python version is slightly different, or they're
missing a system library some package needs, it might not run for them
even though the code is identical.

Docker solves this by packaging the app **and everything it needs to
run** - the exact Python version, every dependency - into one unit
called an **image**. Anyone who runs that image gets the exact same
environment, every time, on any machine that has Docker installed.
That's what makes it deployable to a cloud server: the cloud doesn't
need Python or `uv` installed at all - just Docker.

## The core mental model

- **Dockerfile** - a recipe: the steps to build the image (what base
  system to start from, what to install, what to copy in, what command
  to run when it starts).
- **Image** - the result of following that recipe. A read-only template,
  built once, reused many times. Like a class in code.
- **Container** - a running instance of an image. Like an object created
  from that class - you can start many containers from the same image.

```
Dockerfile  --docker build-->  image  --docker run-->  container (running)
```

## The Dockerfile, explained

```dockerfile
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
```

- `FROM python:3.11-slim` - start from a minimal Python 3.11 image
  (matches the version this project was built with).
- `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/` - we use `uv`
  for package management everywhere else in this project, so we use it
  here too. This copies uv's binary straight from its own official
  image - no `pip install uv` step needed.
- `WORKDIR /app` - everything after this happens inside `/app` in the
  container.
- `COPY requirements.txt .` then `RUN uv pip install ...` **before**
  `COPY . .` - this is deliberate. Docker caches each step. As long as
  `requirements.txt` doesn't change, this install step is skipped on
  future builds even if you've changed the app code - much faster
  rebuilds. Copying all the code first would break that cache on every
  single code change.
- `EXPOSE 8501` - Streamlit's default port. Documentation only - it
  doesn't actually publish the port (see `-p` below).
- `CMD [...]` - what runs when the container starts.
  `--server.address=0.0.0.0` is required: Streamlit only listens on
  `localhost` by default, which is unreachable from outside the
  container without it.

`.dockerignore` keeps `.env`, the local venv, `logs/`, `.git`, and other
non-essential folders out of the image - smaller image, and secrets
never get baked in (see "Is it safe to share this image?" below).

## Two real gotchas we hit building this

1. **Modern Docker builds don't auto-load locally.** `docker build -t
   hr-assistant .` succeeded but `docker images` didn't show it - a
   warning said the result stayed in the build cache only. Fix: add
   `--load` - `docker build --load -t hr-assistant .`.
2. **`--env-file` is stricter than Python's `.env` loading.** Our
   `.env` has lines like `GROQ_API_KEY = "value"` (spaces around `=`,
   quotes) - `python-dotenv` handles that fine, but `docker run
   --env-file` rejects it: `variable 'GROQ_API_KEY ' contains
   whitespaces`. Docker's format is strict: `KEY=value`, no spaces, no
   quotes needed.

   **The fix** - generate a Docker-friendly copy from your real `.env`
   (this strict format is still perfectly valid for `python-dotenv` too,
   so you could just reformat `.env` itself instead of keeping a
   separate copy, if you prefer one file):
   ```bash
   sed -E 's/^([A-Z_]+)\s*=\s*"?([^"]*)"?\s*$/\1=\2/' .env > .env.docker
   ```
   Then use `--env-file .env.docker` in every `docker run` command below
   instead of `--env-file .env`. (`docker compose`'s `env_file:` doesn't
   have this problem - see `docs/08_docker_compose.md`.)

## Commands - basics

| Command | What it does | Example |
|---|---|---|
| `docker build --load -t <name> .` | Build an image from the Dockerfile in the current folder, tag it `<name>`, and load it into local Docker. | `docker build --load -t hr-assistant .` |
| `docker run -d --name <n> -p <host>:<container> --env-file <file> <image>` | Start a container from an image, in the background (`-d`), with a name, a port mapping, and env vars loaded from a file. | `docker run -d --name hr-assistant-app -p 8501:8501 --env-file .env.docker hr-assistant` (see the gotcha above for why `.env.docker`, not `.env`) |
| `docker ps` | List running containers. | `docker ps` |
| `docker ps -a` | List **all** containers, including stopped ones. | `docker ps -a` |
| `docker logs <container>` | See a container's output so far. | `docker logs hr-assistant-app` |
| `docker logs -f <container>` | Stream a container's logs live, as they happen. | `docker logs -f hr-assistant-app` |
| `docker images` | List images you've built or pulled. | `docker images` |

## Commands - stopping and cleaning up (terminate everything)

Run these when you're done, in this order:

| Command | What it does | Example |
|---|---|---|
| `docker stop <container>` | Gracefully stop a running container. | `docker stop hr-assistant-app` |
| `docker rm <container>` | Delete a stopped container (frees its name for reuse). | `docker rm hr-assistant-app` |
| `docker stop <c> && docker rm <c>` | Stop and remove in one line. | `docker stop hr-assistant-app && docker rm hr-assistant-app` |
| `docker rmi <image>` | Delete the image itself (only works once no container is using it). | `docker rmi hr-assistant` |

Quick shortcut: `docker rm -f <container>` stops **and** removes in one
command, if you don't need the graceful-stop step.

## Commands - advanced

| Command | What it does | Example |
|---|---|---|
| `docker exec -it <container> bash` | Open a live shell inside a *running* container - useful for poking around or debugging. | `docker exec -it hr-assistant-app bash` |
| `docker exec <container> <cmd>` | Run one command inside a running container without an interactive shell. | `docker exec hr-assistant-app python -c "import hr_assistant"` |
| `docker inspect <container>` | Dump full JSON config - env vars, network, mounts, everything - for a container or image. | `docker inspect hr-assistant-app` |
| `docker run --name <n> ...` | Give a container a fixed name instead of a random one, so you can refer to it consistently in later commands. | `docker run --name hr-assistant-app ...` |

## Verified working

Built the real image, ran it with the real `.env` (normalized for
Docker's stricter format), and confirmed, live:
- `docker ps` showed the container running, port `8501` mapped.
- `curl http://localhost:8501/_stcore/health` returned `200`.
- The deeper check: `docker exec`'d into the running container and
  called `build_hr_assistant()` / `ask()` directly - confirmed real
  HTTP `200`s from Qdrant Cloud, Portkey (`provider=@hrpolicy`), and
  Groq, and got back the correct answer: *"You're entitled to 20 paid
  annual leave days per calendar year..."* - proof the whole pipeline
  genuinely works inside the container, not just that Streamlit's
  process is alive.

## Files changed

| File | What changed |
|------|--------------|
| `Dockerfile` | **New file.** Builds the app image using `uv` for installs. |
| `.dockerignore` | **New file.** Keeps `.env`, the venv, logs, and non-essential folders out of the image. |

## Docker Hub - sharing the image

A **registry** (Docker Hub is the default public one) is where built
images live so other people - or a cloud server - can `docker pull`
them instead of rebuilding from source every time.

```
docker build  ->  image (local only)
docker tag    ->  image labeled with your Docker Hub username
docker push   ->  image uploaded to Docker Hub
docker pull   ->  anyone can download and run it, anywhere
```

**Is it safe to share this image publicly?** Yes - `.dockerignore`
keeps `.env` out of the build context entirely, so no API keys are
baked into the image. Secrets are only ever passed in at `docker run`
time via `--env-file`, never stored in the image itself.

| Command | What it does | Example |
|---|---|---|
| `docker login` | Authenticate with Docker Hub (prompts for username/password or token). | `docker login` |
| `docker tag <image> <username>/<image>:<tag>` | Label a local image with the name it'll have on Docker Hub. | `docker tag hr-assistant dcrazzy/hr-assistant:latest` |
| `docker push <username>/<image>:<tag>` | Upload the tagged image to Docker Hub. | `docker push dcrazzy/hr-assistant:latest` |
| `docker pull <username>/<image>:<tag>` | Download an image from Docker Hub (what a cloud server would do). | `docker pull dcrazzy/hr-assistant:latest` |
| `docker logout` | End your Docker Hub session on this machine. | `docker logout` |
| `docker rmi <username>/<image>:<tag>` | Remove the tagged copy locally once you're done (the pushed copy stays on Docker Hub). | `docker rmi dcrazzy/hr-assistant:latest` |

## Assignment for students

1. Multi-stage build: the current image includes `jupyter`/`ipykernel`
   from `requirements.txt`, which the deployed app never uses. Split
   the Dockerfile into a `build` stage and a slimmer final stage that
   only copies what's needed to run.
2. Add a `HEALTHCHECK` instruction to the Dockerfile using
   `_stcore/health`, and watch `docker ps` show `healthy`/`unhealthy`.
3. Run `main.py` (the CLI demo) instead of the Streamlit app, from the
   *same* image, without touching the Dockerfile: `docker run --env-file
   .env.docker hr-assistant python main.py`.
