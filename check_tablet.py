import paramiko, subprocess, sys, time
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

REMOTE = "/data/data/com.termux/files/home/home-dashboard"
sftp = c.open_sftp()

def push(local, remote):
    sftp.put(local, f"{REMOTE}/{remote}")
    print(f"  {remote}")

# Opret mapper
ssh(f"mkdir -p {REMOTE}/backend {REMOTE}/frontend {REMOTE}/scripts")

# Push alle filer
for f in ["backend/main.py", "backend/aula_client.py", 
          "backend/aula_playwright.py", "backend/aula_playwright_android.py",
          "backend/__init__.py"]:
    push(f.replace("/", "\\"), f)

push(r"frontend\index.html", "frontend/index.html")
push(r"frontend\settings.html", "frontend/settings.html")
push(r"scripts\login_node.js", "scripts/login_node.js")
push(r"requirements.txt", "requirements.txt")
push(r".env", ".env")

sftp.close()

# Patch playwright
ssh(r"sed -i \"s/hostPlatform: '<unknown>'/hostPlatform: 'ubuntu22.04-arm64'/\" " + 
    f"{REMOTE}/node_modules/playwright-core/lib/server/utils/hostPlatform.js 2>/dev/null || echo skip_patch1")
ssh(r'sed -i "s/if (process.platform === \"linux\")/if (process.platform === \"linux\" || process.platform === \"android\")/" ' +
    f"{REMOTE}/node_modules/playwright-core/lib/server/registry/index.js 2>/dev/null || echo skip_patch2")

# Start server
ssh(f"pkill -f uvicorn 2>/dev/null; sleep 1")
ssh(f"> {REMOTE}/server.log")
c.exec_command(f"cd {REMOTE} && nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 >> server.log 2>&1 &", timeout=3)
time.sleep(7)

ssh(f"cat {REMOTE}/server.log | tail -5")
ssh("curl -s http://127.0.0.1:8000/api/config", timeout=10)
c.close()
