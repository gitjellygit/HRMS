#!/usr/bin/env bash
set -Eeuo pipefail
TARGET_SHA="${1:?Pass verified SHA}"
[[ "$TARGET_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "Invalid SHA"; exit 1; }
cd /opt/jellygit/hrms
test -f .env
git diff --quiet && git diff --cached --quiet
git fetch --no-tags origin main
git cat-file -e "$TARGET_SHA^{commit}"
PREVIOUS_SHA="$(git rev-parse HEAD)"
if [[ "$PREVIOUS_SHA" == "$TARGET_SHA" ]]; then echo "Already deployed"; exit 0; fi
if git diff --name-only "$PREVIOUS_SHA" "$TARGET_SHA" -- backend/migrations/ docker-compose.yml | grep -q .; then
 echo "Schema/migration or Compose change: manual review required"; exit 1
fi
rollback() {
 code=$?
 trap - ERR
 echo "Rollback to $PREVIOUS_SHA attempted"
 git checkout --detach "$PREVIOUS_SHA"
 docker compose build api web leave-email-worker || true
 docker compose up -d --no-deps api web || true
 exit "$code"
}
trap rollback ERR
git checkout --detach "$TARGET_SHA"
docker compose config --quiet
docker compose build api web leave-email-worker
docker compose up -d --no-deps api web
if docker compose ps --services --status running | grep -qx leave-email-worker; then
 docker compose up -d --no-deps leave-email-worker
fi
healthy=false
for attempt in {1..20}; do
 if curl -fsS --max-time 8 http://127.0.0.1:8000/health >/dev/null 2>&1 &&
    curl -fsS --max-time 8 https://api-hrms.jellygit.com/health >/dev/null 2>&1 &&
    curl -fsS --max-time 8 https://hrms.jellygit.com >/dev/null 2>&1; then
  healthy=true; break
 fi
 sleep 3
done
[[ "$healthy" == true ]] || { echo "Post-deploy health failed"; false; }
trap - ERR
echo "Successfully deployed $TARGET_SHA"
