FROM python:3.12-slim-bullseye AS builder

RUN apt update -y && apt upgrade -y && apt install curl git -y
RUN curl -LsSf https://astral.sh/uv/0.7.11/install.sh | sh

ENV PATH="${PATH}:/root/.local/bin"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN touch README.md

RUN --mount=type=ssh uv venv -v
RUN --mount=type=ssh uv sync --no-group dev --no-group docs -v

COPY ontocast ./ontocast
COPY README.md ./

CMD ["uv", "run", "python", "serve", "--env-path", ".env", "--ontology-path", "./data/ontologies", "--working-directory", "./cwd"]
