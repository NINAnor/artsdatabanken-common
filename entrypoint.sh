#!/bin/sh

SQLITE_PATH="/usr/bin/sqlite3" ./generate.sh

exec "$@"
