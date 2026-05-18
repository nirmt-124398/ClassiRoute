#!/bin/sh
set -e

# Wait for the database port to be reachable.
if [ -n "$DATABASE_URL" ]; then
    echo "Waiting for database..."
    host=$(echo "$DATABASE_URL" | sed -E 's|^.*@([^:/]+).*$|\1|')
    port=$(echo "$DATABASE_URL" | sed -E 's|^.*:([0-9]+)/.*$|\1|')
    port=${port:-5432}
    python3 -c "
import socket, time
while True:
    try:
        s = socket.create_connection(('$host', $port), timeout=2)
        s.close()
        break
    except (OSError, ConnectionRefusedError):
        time.sleep(1)
" && echo " Database ready."
fi

exec "$@"
