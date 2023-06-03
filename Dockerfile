FROM python:3.10.6-slim

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip

RUN git clone https://github.com/D00mSlayer/timeline-visitor-server.git server-app
WORKDIR /app/server-app

RUN python3 -m venv .venv
SHELL ["/bin/bash", "-c"]
RUN source .venv/bin/activate
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5001
ENTRYPOINT [ "python", "run.py" ]
