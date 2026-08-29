# this is a python image
FROM python:3.11-slim  

# use uv for venv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# make a dir for a code
WORKDIR /app

# pull the req
COPY requirements.txt .

# run the req file 
RUN uv pip install --system --no-cache -r requirements.txt

# copy my code

COPY . . 

# expose where your app will run 
# PORT MAPPING 

EXPOSE 8501

# how to run my app 
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]





