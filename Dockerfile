FROM python:3.10 AS base
WORKDIR /src

FROM base AS build
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install pdm
COPY pyproject.toml pdm.lock ./
RUN --mount=type=cache,target=/root/.cache/pdm \
    pdm install --no-self
COPY generate.py ./
RUN pdm run ./generate.py

FROM base

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install datasette
COPY --from=build /src/common.sqlite .

EXPOSE 8001/TCP
CMD ["datasette", "serve", "-h", "0.0.0.0", "-i", "common.sqlite"]
