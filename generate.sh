#!/bin/sh

SOURCE_PATH="https://miljodata-test.s3-int-1.nina.no/common/artsdatabanken"

set -ex

sling run --src-stream "$SOURCE_PATH/nortaxa.parquet" --tgt-conn "sqlite://common.sqlite" --tgt-object "nortaxa"
sling run --src-stream "$SOURCE_PATH/rodliste2021.parquet" --tgt-conn "sqlite://common.sqlite" --tgt-object "rodliste2021"
sling run --src-stream "$SOURCE_PATH/fremmedartslista2023.parquet" --tgt-conn "sqlite://common.sqlite" --tgt-object "fremmedartslista2023"

sqlite3 common.sqlite < fts.sql
