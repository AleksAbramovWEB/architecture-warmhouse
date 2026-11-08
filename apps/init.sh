#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

docker compose up --build --detach --wait --wait-timeout 120
docker compose ps

app_address="$(docker compose port app 8080)"
temperature_address="$(docker compose port temperature-api 8081)"
echo "Smart Home API: http://${app_address}"
echo "Temperature API: http://${temperature_address}"
printf 'Logs: docker compose -f %q logs -f\n' "$PWD/docker-compose.yml"
printf 'Stop: docker compose -f %q down (database volume is preserved)\n' "$PWD/docker-compose.yml"
