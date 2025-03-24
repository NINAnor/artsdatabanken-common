FROM busybox AS deps

WORKDIR /usr/local/bin/

ADD https://github.com/slingdata-io/sling-cli/releases/download/v1.4.4/sling_linux_amd64.tar.gz sling.tar.gz
RUN tar xzf sling.tar.gz sling && rm sling.tar.gz

FROM python:3.12-slim
COPY --from=deps /usr/local/bin /usr/local/bin

RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
    --mount=type=cache,sharing=locked,target=/var/lib/apt \
    rm /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && \
    apt-get install -qy --no-install-recommends \
        sqlite3

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install datasette datasette-reconcile

WORKDIR /app
ADD generate.sh metadata.json fts.sql ./
ADD entrypoint.sh /

ENTRYPOINT [ "/entrypoint.sh" ]

EXPOSE 8001/TCP
CMD ["datasette", "serve", "-h", "0.0.0.0", "--metadata", "metadata.json", "-i", "common.sqlite"]
