#!/bin/bash
# Olivenet Social Bot Starter Script

cd /opt/olivenet-social-bot
export PYTHONPATH=/opt/olivenet-social-bot
export PYTHONUNBUFFERED=1

# Activate venv and run
source venv/bin/activate
exec python3 -u app/telegram_pipeline.py
