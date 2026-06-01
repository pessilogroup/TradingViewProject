# 🤖 AGENT DEPLOYMENT INSTRUCTION PROMPT: SERVER A SETUP & DEPLOYMENT

> **INSTRUCTION FOR THE AGENT:** You are an expert SRE and DevOps AI assistant. Your task is to connect to the user's newly initialized VPS (Server A - Ingress Gateway) via SSH, install all required dependencies (Docker, Tailscale, Cloudflared), transfer the VBS (VPS Buffer Service) files, and deploy the service.
> Use the environment facts and connection details provided below. Work safely, securely, and verify every step.

---

## 🌐 1. Environment & Connection Facts

* **Target Host IP:** `103.82.21.77`
* **SSH Configuration Name:** `trading-gateway` (Configured in local `~/.ssh/config`)
* **SSH Username:** `botuser`
* **SSH Private Key (Local Path):** `C:/Users/Son/.ssh/id_ed25519_trading`
* **Target OS:** Debian 11 (Bullseye)
* **Sudo Password:** `TradingBot2026!`
* **Local Workspace Root:** `C:\Users\Son\TRADING_CLONE`

---

## 📋 2. Execution Plan & Tasks

### Task 2.1: Establish SSH Connection & Update Package Lists
SSH into the server using `trading-gateway` config.
Check that you are logged in as `botuser` and verify the OS environment.
```bash
uname -a && cat /etc/os-release
```

### Task 2.2: Install Docker CE & Docker Compose V2
Execute the following commands to install Docker:
```bash
# 1. Install keys and repo
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 2. Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 3. Add botuser to docker group
sudo usermod -aG docker botuser

# 4. Limit container log sizes
sudo tee /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
EOF

# 5. Restart docker
sudo systemctl restart docker
```

### Task 2.3: Install & Configure Tailscale VPN
1. Install Tailscale:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   ```
2. Start Tailscale connection:
   ```bash
   sudo tailscale up
   ```
3. **Action:** Log the login URL printed by Tailscale to the user so they can click and approve it.
4. Set hostname:
   ```bash
   sudo tailscale set --hostname=server-a-gateway
   ```
5. Fetch and log the internal Tailscale IP (`100.x.x.x`):
   ```bash
   tailscale ip -4
   ```

### Task 2.4: Copy and Configure VBS Files from Local to VPS
1. **On your LOCAL environment**, copy the `vbs/` folder and `docker-compose.vbs.yml` from `C:\Users\Son\TRADING_CLONE` to Server A:
   ```powershell
   scp -r C:\Users\Son\TRADING_CLONE\vbs trading-gateway:/home/botuser/
   scp C:\Users\Son\TRADING_CLONE\docker-compose.vbs.yml trading-gateway:/home/botuser/
   ```
2. **On the REMOTE VPS**, create the `vbs/.env` file:
   ```bash
   cat << 'EOF' > /home/botuser/vbs/.env
   PORT=5000
   HOST=0.0.0.0

   # Secret token to authenticate TradingView webhook signals and Local Bot pulling.
   BUFFER_SECRET=9ea7c89fbfd63a8a2bc8644e99da54fc5b2c7e098fe1d9e2b10a4e320f781a7b

   # Time to Live for each signal in hours
   SIGNAL_TTL_HOURS=4.0

   # Timeout in minutes for local bot to acknowledge a signal
   DISPATCH_TIMEOUT_MINUTES=5.0

   # Max queue size of pending signals
   MAX_QUEUE_SIZE=1000

   # Cron settings
   CLEANUP_INTERVAL_MINUTES=15
   AUDIT_RETENTION_DAYS=7

   # SQLite database path
   DB_PATH=data/signal_queue.db
   EOF
   ```

### Task 2.5: Deploy VBS Container
On the VPS, build and launch the VBS container:
```bash
docker compose -f /home/botuser/docker-compose.vbs.yml up -d --build
```
Verify the container status:
```bash
docker ps
```

### Task 2.6: Local Verification (Smoke Test)
Call the health check endpoint inside the VPS to ensure the service is running and connected to SQLite:
```bash
curl http://localhost:5000/health
```
**Expected response:**
`{"status":"healthy","uptime_seconds":...,"db":"ok","pending_count":0}`

---

## 🔒 3. Inviolable Security & Operational Constraints

1. **NO ROOT RUNNING:** Do not run the Docker container or service under the `root` account. Always use `botuser` and `sudo` where elevated rights are required.
2. **NO EXTERNAL PORT EXPOSURE:** Do not modify UFW or open port `5000` to the public internet. The VBS queue must only be accessed locally, via Tailscale, or through Cloudflare Tunnel.
3. **LOG LIMITATIONS:** Always ensure Docker daemon logs are restricted using `daemon.json` configuration as outlined in Task 2.2.

---

*Begin execution by establishing the SSH connection to the VPS and setting up Docker. Report your progress stage by stage.*
