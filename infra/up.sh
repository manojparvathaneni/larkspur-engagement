#!/usr/bin/env bash
# Starts Larkspur on cooper. Seeds the database the first time only.
#   ./infra/up.sh            start, seeding if empty
#   ./infra/up.sh --reseed   wipe and rebuild Larkspur's history from the seed
set -euo pipefail
cd "$(dirname "$0")"
[ -f ../.env ] || { echo "missing .env; copy .env.example to .env and fill it in"; exit 1; }
ln -sf ../.env .env  # compose reads variables from .env beside compose.yaml
set -a; . ../.env; set +a
for v in POSTGRES_PASSWORD FCWS_PASSWORD DESKLINE_TOKEN LARKSPUR_SCENARIO_KEY; do
  [ -n "${!v:-}" ] || { echo "$v is empty in .env"; exit 1; }
done
free_mb=$(free -m | awk '/^Mem:/ {print $7}')
[ "$free_mb" -gt 1500 ] || { echo "only ${free_mb} MB available; Larkspur needs about 1.5 GB to start"; exit 1; }

docker compose build
docker compose up -d db
seeded=$(docker compose exec -T db psql -U larkspur -d larkspur -tAc "select to_regclass('fc.shpmst') is not null" || echo f)
if [ "${1:-}" = "--reseed" ] || [ "$seeded" != "t" ]; then
  docker compose stop world 2>/dev/null || true
  echo "seeding Larkspur's history, about a minute"
  docker compose run --rm seed
fi
docker compose up -d freightcore deskline world
./smoke.sh
