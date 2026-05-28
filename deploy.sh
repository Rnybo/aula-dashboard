#!/data/data/com.termux/files/usr/bin/bash
export PATH="/data/data/com.termux/files/usr/bin:"
export HOME="/data/data/com.termux/files/home"

# Stop gammel server
pkill -f uvicorn 2>/dev/null
sleep 2

# Kopiér nye filer fra sdcard
cp /sdcard/aula-dashboard/backend/main.py ~/aula-dashboard/backend/main.py
cp /sdcard/aula-dashboard/backend/aula_client.py ~/aula-dashboard/backend/aula_client.py
cp /sdcard/aula-dashboard/frontend/index.html ~/aula-dashboard/frontend/index.html
cp /sdcard/aula-dashboard/frontend/settings.html ~/aula-dashboard/frontend/settings.html

# Start ny server
cd ~/aula-dashboard
nohup python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 >> /sdcard/server.log 2>&1 &
sleep 3
pgrep -f uvicorn && echo "SERVER OK" || echo "SERVER FEJLEDE"