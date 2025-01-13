#!/usr/bin/with-contenv sh
PORT=$(jq -r ".httpPort" "/app/config/${CTBVER}/server.json")
nc -w 1 127.0.0.1 $PORT || exit 1
