#!/bin/sh
set -eu

BOT_DIR="/volume1/docker/stock-bot"
WUD_DIR="/volume1/docker/wud"

# Validate both Compose projects before changing either one.
(cd "$BOT_DIR" && sudo docker compose config --quiet)
(cd "$WUD_DIR" && sudo docker compose config --quiet)

# Pull the current image and apply the cron service configuration.
(
    cd "$BOT_DIR"
    sudo docker compose pull stock-bot-cron
    sudo docker compose up -d --no-deps stock-bot-cron
)

# Apply the WUD service configuration.
(cd "$WUD_DIR" && sudo docker compose up -d wud)
