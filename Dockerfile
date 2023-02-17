FROM python:3.10 AS base
WORKDIR /src

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install pdm
COPY pyproject.toml pdm.lock ./
RUN --mount=type=cache,target=/root/.cache/pdm \
    pdm install --no-self --group datasette
COPY generate.py ./
RUN pdm run ./generate.py
COPY metadata.json .

EXPOSE 8001/TCP
CMD ["pdm", "run", "datasette", "serve", "-h", "0.0.0.0", "--metadata", "metadata.json", "-i", "common.sqlite"]
