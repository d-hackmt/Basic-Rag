# Docker - Full Command Flow

One continuous run, start to finish - check Docker is ready, build,
run, push to Docker Hub, pull it back, then clean up completely. Every
command has a comment explaining what it does and why, in simple
words. For the deeper "why does this work this way" explanations, see
[07_docker.md](07_docker.md) - this file is just the flow, meant to be
followed top to bottom (or copy-pasted as a script).

```bash
# ============================================================
# STEP 1 - Is Docker even here, and actually running?
# The CLI can be installed without Docker Desktop running - `docker ps`
# is the real test, since it has to talk to the Docker daemon.
# ============================================================
docker --version
docker ps
# if this errors with "cannot connect to the Docker daemon", start
# Docker Desktop first, then try again.


# ============================================================
# STEP 2 - What's already on this machine?
# Good habit before building anything - know what's yours vs. what
# was already sitting here from earlier work.
# ============================================================
docker images
docker ps -a


# ============================================================
# STEP 3 - Build our image
# --load matters: modern Docker can leave a build result in a cache
# only, invisible to `docker images`, unless you add --load.
# ============================================================
docker build --load -t hr-assistant .

# confirm it's really there
docker images hr-assistant


# ============================================================
# STEP 4 - Get our secrets into a Docker-friendly file
# Our .env has spaces/quotes around "=" (fine for Python, not for
# Docker's --env-file, which is stricter). This makes a clean copy.
# ============================================================
sed -E 's/^([A-Z_]+)\s*=\s*"?([^"]*)"?\s*$/\1=\2/' .env > .env.docker


# ============================================================
# STEP 5 - Spin up the container
# -d = run in the background. --name = a name we can refer back to.
# -p 8501:8501 = map the container's port to the same port on our
# machine. --env-file = load the secrets from the file we just made.
# ============================================================
docker run -d --name hr-assistant-app -p 8501:8501 --env-file .env.docker hr-assistant

# confirm it's running, then watch it live
docker ps
docker logs -f hr-assistant-app
# (Ctrl+C stops watching the logs - it does NOT stop the container)

# now open http://localhost:8501 in a browser - the real app, running
# inside a container.


# ============================================================
# STEP 6 - Push it to Docker Hub
# Docker Hub is a registry - a place images live so other people (or
# a cloud server) can download and run them without ever seeing your
# source code or rebuilding anything.
# ============================================================

# log in (prompts for your Docker Hub username + password or token)
docker login

# "tag" = label the image with your Docker Hub username, so Docker
# Hub knows which account's repository to upload it to
docker tag hr-assistant dcrazzy/hr-assistant:latest

# actually upload it
docker push dcrazzy/hr-assistant:latest


# ============================================================
# STEP 7 - Delete it from this machine
# This proves the next step (pull) is a real download from Docker
# Hub, not just reusing something already sitting on our machine.
# ============================================================
docker rmi dcrazzy/hr-assistant:latest

# confirm the Docker Hub tag is gone (the original "hr-assistant"
# local tag from Step 3 is untouched - only the tagged copy is deleted)
docker images


# ============================================================
# STEP 8 - Pull it back down
# This is exactly what a teammate, or a cloud server, would run to
# get your app - a plain download, no source code involved.
# ============================================================
docker pull dcrazzy/hr-assistant:latest
docker images

# run the pulled copy on a different port, to prove it's the same app
docker run -d --name hr-assistant-from-hub -p 8502:8501 --env-file .env.docker dcrazzy/hr-assistant:latest
docker ps
# check http://localhost:8502 - same app, this time from Docker Hub


# ============================================================
# STEP 9 - Terminate everything
# Stop and remove every container we made, delete every image, and
# log out of Docker Hub. Leaves the machine exactly as it was.
# ============================================================
docker stop hr-assistant-app hr-assistant-from-hub
docker rm hr-assistant-app hr-assistant-from-hub
docker rmi hr-assistant dcrazzy/hr-assistant:latest
docker logout

# confirm everything is really gone
docker ps -a
docker images

# ============================================================
# DONE - docker branch flow complete.
# ============================================================
```
