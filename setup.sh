#!/bin/bash
set -e

echo "Olivenet Social Bot Kurulumu"
echo "================================"

# 1. Bagimliliklari yukle
echo "Python bagimliliklari yukleniyor..."
pip install -r requirements.txt

# 2. Playwright kur
echo "Playwright Chromium kuruluyor..."
playwright install chromium
playwright install-deps

# 3. .env kontrolu
if [ ! -f .env ]; then
    echo ".env dosyasi bulunamadi!"
    echo ".env.example'dan kopyalaniyor..."
    cp .env.example .env
    echo ""
    echo "ONEMLI: .env dosyasini duzenleyip token'lari girin:"
    echo "   nano .env"
    echo ""
    exit 1
fi

# 4. outputs klasoru
mkdir -p outputs

# 5. Test
echo "Sistem testi..."
python3 -c "from app.config import get_settings; s = get_settings(); print(f'Config OK - Chat ID: {s.telegram_admin_chat_id}')"

echo ""
echo "Kurulum tamamlandi!"
echo ""
echo "Bot'u baslatmak icin:"
echo "  python3 app/telegram_bot.py"
echo ""
echo "Systemd servisi olarak kurmak icin:"
echo "  sudo cp olivenet-social.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable olivenet-social"
echo "  sudo systemctl start olivenet-social"
