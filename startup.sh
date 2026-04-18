#!/bin/bash
set -e

# Update and install Docker using the official repo to ensure docker-compose-plugin is available
apt-get update
apt-get install -y ca-certificates curl gnupg git

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
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

# Clone LetterFeed repository
if [ ! -d ".git" ]; then
  git clone https://github.com/LeonMusCoden/LetterFeed.git .
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

# Start LetterFeed
docker compose up -d
