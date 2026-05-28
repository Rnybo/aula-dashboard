#!/data/data/com.termux/files/usr/bin/bash
export PATH=/data/data/com.termux/files/usr/bin:
pkill -f uvicorn 2>/dev/null
sleep 2
cd /data/data/com.termux/files/home/aula-dashboard
nohup python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 >> /sdcard/server.log 2>&1 &
echo "Server started PID $!"