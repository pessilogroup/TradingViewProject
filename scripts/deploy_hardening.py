#!/usr/bin/env python3
"""
deploy_hardening.py — Automation script for OS-level Hardening on Server A & Server C.
Configures UFW, Fail2ban, Chrony NTP, and Docker daemon log rotation.
"""
import os
import sys
import subprocess

# SSH configuration parameters
SERVER_A_IP = "103.82.21.77"    # Public IP of Server A
SERVER_A_USER = "botuser"       # Deployment user with sudo privileges
SERVER_A_KEY = os.path.expanduser("~/.ssh/pk/sshkey-serverc.pem")

SERVER_C_IP = "103.82.193.97"  # Public IP of Server C
SERVER_C_USER = "botuser"       # Deployment user with sudo privileges
SERVER_C_KEY = os.path.expanduser("~/.ssh/pk/sshkey-serverc.pem")

import shlex

def run_ssh_command(ip, user, key_path, cmd):
    """Run ssh command as root and return output."""
    if user != "root":
        cmd = f"sudo bash -c {shlex.quote(cmd)}"
    ssh_cmd = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=no",
        "-i", key_path,
        f"{user}@{ip}",
        cmd
    ]
    print(f"\n[SSH EXEC] {user}@{ip}: {cmd[:80]}...")
    res = subprocess.run(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res.returncode, res.stdout, res.stderr

def harden_server_a():
    """Harden Server A (Debian 12 Gateway)."""
    print("\n=======================================================")
    print("           HARDENING SERVER A (GATEWAY)                ")
    print("=======================================================")
    
    commands = [
        # 1. Update package list
        "apt-get update",
        
        # 2. NTP Time Sync (Chrony)
        "apt-get install -y chrony",
        """cat << 'EOF' > /etc/chrony/chrony.conf
server 0.pool.ntp.org iburst
server 1.pool.ntp.org iburst
server time.google.com iburst prefer
server time.cloudflare.com iburst
makestep 1.0 3
driftfile /var/lib/chrony/chrony.drift
logdir /var/log/chrony
log tracking measurements statistics
maxdistance 0.1
EOF""",
        "systemctl enable --now chrony || systemctl enable --now chronyd",
        "systemctl restart chrony || systemctl restart chronyd",
        
        # 3. Fail2ban setup
        "apt-get install -y fail2ban",
        """cat << 'EOF' > /etc/fail2ban/jail.local
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port    = ssh
filter  = sshd
logpath = /var/log/auth.log
EOF""",
        "systemctl enable --now fail2ban",
        "systemctl restart fail2ban",
        
        # 4. Docker CE install & configuration
        """if ! command -v docker &> /dev/null; then
            apt-get install -y ca-certificates curl gnupg
            install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
            chmod a+r /etc/apt/keyrings/docker.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
            apt-get update
            apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        fi""",
        """mkdir -p /etc/docker && cat << 'EOF' > /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
EOF""",
        "systemctl enable docker",
        "systemctl restart docker",
        
        # 5. UFW Firewall setup (Strict rules)
        "apt-get install -y ufw",
        "ufw default deny incoming",
        "ufw default allow outgoing",
        "ufw allow 22/tcp",
        "ufw allow in on tailscale0",
        "echo 'y' | ufw enable",
        "systemctl enable --now ufw",
        "systemctl restart ufw"
    ]
    
    for cmd in commands:
        code, out, err = run_ssh_command(SERVER_A_IP, SERVER_A_USER, SERVER_A_KEY, cmd)
        if code != 0:
            print(f"[ERROR] Command failed with code {code}.\nStderr: {err}\nStdout: {out}")
            return False
        else:
            print(f"[SUCCESS] Command output:\n{out.strip()}")
            
    print("\n[OK] Server A hardening completed successfully!")
    return True

def harden_server_c():
    """Harden Server C (Oracle Linux 9 AI Core)."""
    print("\n=======================================================")
    print("           HARDENING SERVER C (AI CORE)                ")
    print("=======================================================")
    
    commands = [
        # 1. EPEL & Chrony/Fail2ban Install
        "dnf install -y oracle-epel-release-el9 || dnf install -y epel-release",
        "dnf install -y chrony fail2ban",
        
        # 2. NTP Time Sync (Chrony)
        """cat << 'EOF' > /etc/chrony.conf
server 0.pool.ntp.org iburst
server 1.pool.ntp.org iburst
server time.google.com iburst prefer
server time.cloudflare.com iburst
driftfile /var/lib/chrony/drift
makestep 1.0 3
rtcsync
logdir /var/log/chrony
EOF""",
        "systemctl enable --now chronyd",
        "systemctl restart chronyd",
        
        # 3. Fail2ban setup
        """cat << 'EOF' > /etc/fail2ban/jail.local
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port    = ssh
logpath = /var/log/secure
backend = systemd
EOF""",
        "systemctl enable --now fail2ban",
        "systemctl restart fail2ban",
        
        # 4. Docker log limits configuration
        """mkdir -p /etc/docker && cat << 'EOF' > /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
EOF""",
        "systemctl enable docker",
        "systemctl restart docker",
        
        # 5. Firewalld configuration
        "systemctl enable --now firewalld",
        "firewall-cmd --permanent --add-service=ssh",
        "firewall-cmd --permanent --zone=trusted --add-interface=tailscale0",
        "firewall-cmd --reload"
    ]
    
    for cmd in commands:
        code, out, err = run_ssh_command(SERVER_C_IP, SERVER_C_USER, SERVER_C_KEY, cmd)
        if code != 0:
            print(f"[ERROR] Command failed with code {code}.\nStderr: {err}\nStdout: {out}")
            return False
        else:
            print(f"[SUCCESS] Command output:\n{out.strip()}")
            
    print("\n[OK] Server C hardening completed successfully!")
    return True

def main():
    success_a = harden_server_a()
    success_c = harden_server_c()
    
    if success_a and success_c:
        print("\n=======================================================")
        print("ALL SERVERS HARDENED SUCCESSFULLY!")
        print("=======================================================")
        sys.exit(0)
    else:
        print("\n[FAIL] Hardening failed on one or more servers.")
        sys.exit(1)

if __name__ == "__main__":
    main()
