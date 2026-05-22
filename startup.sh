#!/bin/bash
set -e

# Clear docker space to prevent "No space left on device" errors
docker system prune -a --volumes -f || true
docker image prune -a -f || true
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
gcloud secrets versions access latest --secret="letterfeed-env" > .env

# Generate a random 32-character secret key if not provided in the secret
if ! grep -q "LETTERFEED_SECRET_KEY" .env; then
  SECRET=$(head /dev/urandom | tr -dc A-Za-z0-9 | head -c 32 ; echo '')
  echo "LETTERFEED_SECRET_KEY=$SECRET" >> .env
fi

# Ensure frontend uses the correct backend URL in Docker Compose
echo "LETTERFEED_BACKEND_URL=http://backend:8000" >> .env

# Force pull the latest production docker images (to bypass local cached images)
docker compose pull

# Start LetterFeed
docker compose up -d
