#!/bin/bash
set -e

# Ensure HOME is set for git configuration
export HOME=/root

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

# Keep cloudflared (the Cloudflare Tunnel that fronts the app) up to date from
# Cloudflare's apt repo. Old versions can carry security fixes we must pick up
# (e.g. >= 2026.10.2 drops the compromised eMudhra intermediates). The systemd
# unit from `cloudflared service install` isn't package-owned, so upgrading
# keeps the tunnel config; restart so the running service uses the new binary.
# Non-fatal: a repo hiccup shouldn't stop LetterFeed itself from starting.
if curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg -o /usr/share/keyrings/cloudflare-main.gpg \
  && echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' \
    > /etc/apt/sources.list.d/cloudflared.list \
  && apt-get update \
  && apt-get install -y cloudflared; then
  cloudflared --version
  if systemctl list-unit-files cloudflared.service >/dev/null 2>&1; then
    systemctl restart cloudflared || true
  fi
else
  echo "WARNING: failed to install/upgrade cloudflared" >&2
fi

# Apply Debian security updates and cloudflared releases daily between boots.
# If an update needs a reboot (e.g. kernel), reboot at 04:00 UTC; this script
# then runs again and refreshes everything else.
if apt-get install -y unattended-upgrades; then
  cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
  cat > /etc/apt/apt.conf.d/51letterfeed-unattended-upgrades <<'EOF'
Unattended-Upgrade::Origins-Pattern {
  "origin=Debian,codename=${distro_codename}-security,label=Debian-Security";
  "origin=cloudflared,codename=any";
};
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
EOF
  # The cloudflared package doesn't restart the tunnel when it's upgraded, so
  # restart it whenever the binary changes.
  cat > /etc/systemd/system/cloudflared-restart.path <<'EOF'
[Path]
PathChanged=/usr/bin/cloudflared

[Install]
WantedBy=multi-user.target
EOF
  cat > /etc/systemd/system/cloudflared-restart.service <<'EOF'
[Service]
Type=oneshot
ExecStart=/bin/systemctl try-restart cloudflared.service
EOF
  systemctl daemon-reload
  systemctl enable --now cloudflared-restart.path || true
else
  echo "WARNING: failed to configure unattended-upgrades" >&2
fi

# Prepare application directory
mkdir -p /opt/letterfeed
cd /opt/letterfeed

# Configure git to trust /opt/letterfeed to bypass dubious ownership warnings
git config --global --add safe.directory /opt/letterfeed || true
git config --system --add safe.directory /opt/letterfeed || true

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

# Tear down any running/half-started containers to prevent daemon lock conflicts
docker compose down || true

# Start LetterFeed cleanly
docker compose up -d
