import paramiko, subprocess, time, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
subprocess.run(['adb', 'forward', 'tcp:8022', 'tcp:8022'], capture_output=True)
key = paramiko.RSAKey.from_private_key_file(r'tablet_key')
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('127.0.0.1', port=8022, username='u0_a225', pkey=key, timeout=10)

def ssh(cmd, timeout=30):
    _, out, err = c.exec_command(cmd, timeout=timeout)
    o = out.read().decode('utf-8', errors='replace').strip()
    e = err.read().decode('utf-8', errors='replace').strip()
    if o: print(o)
    if e: print("ERR:", e)

# Ryd flade filer fra roden (ikke git-managed filer)
print("Rydder gammel flad struktur...")
ssh("cd ~/aula-dashboard && rm -f main.py aula_client.py aula_playwright.py aula_playwright_android.py login_node.js")
ssh("rm -rf ~/aula-dashboard/static")

# Pull ny kode
print("Git pull...")
ssh("cd ~/aula-dashboard && git pull origin main", timeout=60)

# Opdater Termux:Boot script
print("Opdaterer boot script...")
ssh("""cat > ~/.termux/boot/start-familieoverblik.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/sh
export PATH="/data/data/com.termux/files/usr/bin:$PATH"
export HOME="/data/data/com.termux/files/home"
cd ~/aula-dashboard
pkill -f uvicorn 2>/dev/null
sleep 2
nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 > ~/aula-dashboard/server.log 2>&1 &
EOF
chmod +x ~/.termux/boot/start-familieoverblik.sh""")

# Genstart server
print("Genstarter server...")
ssh("pkill -f uvicorn 2>/dev/null; sleep 1")
ssh("cd ~/aula-dashboard && rm -rf backend/__pycache__ && "
    "nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &")

time.sleep(5)
ssh("curl -s http://127.0.0.1:8000/api/config", timeout=10)
c.close()
