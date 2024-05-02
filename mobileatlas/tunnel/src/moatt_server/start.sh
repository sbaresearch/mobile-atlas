#!/bin/sh

set +m

gunicorn --log-config "config/log.ini" -b "0.0.0.0:8000" -k uvicorn.workers.UvicornWorker moatt_server.rest.main:app &
moat-tunnel-server --host "0.0.0.0" --port 6666 --config "config/config.toml" "$@" &

wait -n
exit $?
