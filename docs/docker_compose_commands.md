# Docker Compose - Full Command Flow

One continuous run: check Compose is ready, build both services, run
them together, run them individually, push to Docker Hub, then clean
up completely. Every command has a comment explaining what it does and
why, in simple words. For the deeper concepts, see
[08_docker_compose.md](08_docker_compose.md) - this file is just the
flow.

```bash
# ============================================================
# STEP 1 - Is Docker Compose here, and ready?
# ============================================================
docker --version
docker compose version
docker ps
# if this errors with "cannot connect to the Docker daemon", start
# Docker Desktop first.


# ============================================================
# STEP 2 - What's already here?
# ============================================================
docker compose ps -a
docker images


# ============================================================
# STEP 3 - Same env-file fix as the docker branch
# Compose's env_file: is actually more lenient than plain `docker run
# --env-file` (it handles our .env's spaces/quotes fine, verified via
# `docker compose config`) - so this step is here for completeness /
# in case you also run things with plain `docker run` elsewhere, not
# because Compose itself needs it.
# ============================================================
sed -E 's/^([A-Z_]+)\s*=\s*"?([^"]*)"?\s*$/\1=\2/' .env > .env.docker


# ============================================================
# STEP 4 - Build both services' images
# One Dockerfile, two images: "app" and "eval" - same dependencies,
# different command (see docker-compose.yml).
# ============================================================
docker compose build

docker images | grep -i basicrag


# ============================================================
# STEP 5 - Run BOTH services together
# --profile tools includes "eval" too (normally hidden - see Step 6).
# Watch what happens: "app" stays running (it's a service), "eval"
# runs evaluate.py once and then EXITS on its own (it's a job, not a
# service) - that's expected, not a crash.
# ============================================================
docker compose --profile tools up -d

docker compose ps -a
# ^ you should see "app" as Up, and "eval" as Exited (0) - that's correct


# ============================================================
# STEP 6 - Tear that down, then run just ONE service at a time
# ============================================================
docker compose down

# just the app (this is the normal way to start it - eval's profile
# keeps it out automatically, no flag needed)
docker compose up -d app
docker compose ps
# check http://localhost:8501 - the app, running

# just the eval job, on demand, whenever you actually want to spend
# the API/LangSmith budget it costs to run a real evaluation
docker compose run --rm eval


# ============================================================
# STEP 7 - Push the app image to Docker Hub
# Compose names images "<project>-<service>" by default - ours are
# "basicrag-app" and "basicrag-eval". Since both come from the exact
# same Dockerfile, in real projects you'd usually only push the one
# you actually deploy (app) - shown here pushing both for completeness.
# ============================================================
docker login

docker tag basicrag-app dcrazzy/hr-assistant-app:latest
docker tag basicrag-eval dcrazzy/hr-assistant-eval:latest

docker push dcrazzy/hr-assistant-app:latest
docker push dcrazzy/hr-assistant-eval:latest


# ============================================================
# STEP 8 - Delete locally, then pull back down to prove it's real
# ============================================================
docker rmi dcrazzy/hr-assistant-app:latest dcrazzy/hr-assistant-eval:latest

docker pull dcrazzy/hr-assistant-app:latest
docker images | grep -i hr-assistant


# ============================================================
# STEP 9 - Terminate everything
# Stop the app, remove all containers/network Compose created, delete
# every image (local build names + Docker Hub tags), log out.
# ============================================================
docker compose down

docker rmi basicrag-app basicrag-eval dcrazzy/hr-assistant-app:latest dcrazzy/hr-assistant-eval:latest

docker logout

# confirm everything is really gone
docker compose ps -a
docker images

# ============================================================
# DONE - docker-compose branch flow complete.
# ============================================================
```
