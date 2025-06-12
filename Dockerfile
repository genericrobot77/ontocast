FROM python:3.12-slim-bullseye AS builder

RUN apt update -y && apt upgrade -y && apt install curl git -y
RUN curl -LsSf https://astral.sh/uv/0.6.15/install.sh | sh

ENV PATH="${PATH}:/root/.local/bin"
RUN --mount=type=ssh ssh -T git@github.com || true

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN touch README.md
COPY src ./src

RUN mkdir -p -m 0700 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts
RUN --mount=type=ssh uv venv -v
RUN --mount=type=ssh uv sync --no-group dev -v

COPY run ./run
COPY README.md ./

CMD sh -c 'uv run python serve --env-path .env --ontology-path ./data/ontologies --working-directory ./cwd'