#!/bin/bash
set -e

# Clear docker space to prevent "No space left on device" errors.
# This script runs on every VM boot before `docker compose up`, when nothing is
# running, so we prune conservatively:
#   - no --volumes: otherwise the (then-unused) letterfeed_data volume would be
#     deleted, wiping the SQLite database.
#   - no -a: otherwise the tagged compose images (unused pre-`up`) would be
#     deleted and re-downloaded on every boot. `docker compose pull` below still
#     guarantees the latest images; here we only reclaim dangling layers/cache.
docker system prune -f || true
docker image prune -f || true
apt-get clean || true

# Update and install Docker using the official repo to ensure docker-compose-plugin is available
apt-get update
apt-get install -y ca-certificates curl gnupg git

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Prepare application directory
mkdir -p /opt/letterfeed
cd /opt/letterfeed

# Clone or update LetterFeed repository
if [ ! -d ".git" ]; then
  git clone https://github.com/samuelkaminsky/LetterFeed.git .
else
  git fetch origin
  git reset --hard origin/master
fi

# Configure environment
# Fetch settings from Google Secret Manager and write directly to .env
# We assume the secret contains the necessary LETTERFEED_* variables.
OLD_KEY=""
if [ -f .env ]; then
  OLD_KEY=$(grep "LETTERFEED_SECRET_KEY" .env | cut -d'=' -f2-)
fi

gcloud secrets versions access latest --secret="letterfeed-env" > .env

# Restore or generate the secret key if not provided in the secret
if ! grep -q "LETTERFEED_SECRET_KEY" .env; then
  if [ -n "$OLD_KEY" ]; then
    echo "LETTERFEED_SECRET_KEY=$OLD_KEY" >> .env
  else
    SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(32))')
    echo "LETTERFEED_SECRET_KEY=$SECRET" >> .env
  fi
fi

# Ensure frontend uses the correct backend URL in Docker Compose
echo "LETTERFEED_BACKEND_URL=http://backend:8000" >> .env

# Force pull the latest production docker images (to bypass local cached images)
docker compose pull

# Start LetterFeed
docker compose up -d
