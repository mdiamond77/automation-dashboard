#!/bin/bash
# Pushes shared secrets to all private repos in the mdiamond77 org.
# Run this whenever you add a new repo.
#
# Usage: ./sync_github_secrets.sh

set -e

ENV_FILE="$HOME/.mathnasium.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found."
  exit 1
fi

# Load env vars from file
export $(grep -v '^#' "$ENV_FILE" | grep '=' | xargs)

# Verify all secrets are set
for var in RADIUS_USERNAME RADIUS_PASSWORD SMTP_USER SMTP_PASSWORD; do
  if [ -z "${!var}" ]; then
    echo "Error: $var is not set in $ENV_FILE"
    exit 1
  fi
done

# Repos to sync (add new repos here)
REPOS=(
  mdiamond77/mathnasium-hold-reminders
  mdiamond77/mathnasium-birthdays-levelups
  mdiamond77/mathnasium-page-goals
  mdiamond77/radius-cc-lists
  mdiamond77/cc-newsletter-automation
  mdiamond77/mathnasium-appointy-export
  mdiamond77/radius-morning-briefing
  mdiamond77/mathnasium-assessment-email-automation
)

SECRETS=(RADIUS_USERNAME RADIUS_PASSWORD SMTP_USER SMTP_PASSWORD)

echo "Syncing secrets to ${#REPOS[@]} repos..."
echo ""

for repo in "${REPOS[@]}"; do
  echo "→ $repo"
  for secret in "${SECRETS[@]}"; do
    gh secret set "$secret" --repo "$repo" --body "${!secret}"
  done
done

echo ""
echo "Done. Secrets synced to all repos."
