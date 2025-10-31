import os
import json
import time
import requests
from collections import deque
from datetime import datetime

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
ACTIVE_POOL = os.getenv("ACTIVE_POOL")
ERROR_RATE_THRESHOLD = float(os.getenv("ERROR_RATE_THRESHOLD"))
WINDOW_SIZE = int(os.getenv("WINDOW_SIZE"))
ALERT_COOLDOWN_SEC = int(os.getenv("ALERT_COOLDOWN_SEC"))

LOG_FILE = "/var/log/nginx/access.log"


last_pool = ACTIVE_POOL
last_alert_time = datetime.min
request_window = deque(maxlen=WINDOW_SIZE)



def send_slack_alert(message: str):
    """Send formatted alert to Slack with cooldown to prevent spam."""
    global last_alert_time
    now = datetime.utcnow()
    if (now - last_alert_time).total_seconds() < ALERT_COOLDOWN_SEC:
        return  

    payload = {"text": message}
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"[{now}] ✅ Slack alert sent.")
        else:
            print(f"[{now}] ⚠️ Slack returned {response.status_code}: {response.text}")
        last_alert_time = now
    except Exception as e:
        print(f"⚠️ Failed to send Slack alert: {e}")


def tail_f(file_path):
    """Stream lines from a file continuously (like tail -f)."""
    with open(file_path, "r") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.3)
                continue
            yield line.strip()


def analyze_log_entry(entry):
    """Process each log line from Nginx (JSON formatted)."""
    global last_pool

    try:
        data = json.loads(entry)
    except json.JSONDecodeError:
        return 

    pool = data.get("pool")
    release = data.get("release")
    status = int(data.get("status", 0))
    upstream = data.get("upstream_addr")
    request_time = data.get("request_time")
    upstream_status = data.get("upstream_status")

    
    is_error = 1 if status >= 500 else 0
    request_window.append(is_error)

    
    total = len(request_window)
    errors = sum(request_window)
    if total > 10: 
        error_rate = (errors / total) * 100
        if error_rate > ERROR_RATE_THRESHOLD:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            message = (
                f" *High Error Rate Detected*\n"
                f"Error Rate: *{error_rate:.2f}%*\n"
                f"Window: *{errors}/{total} requests*\n"
                f"Timestamp: {timestamp}\n"
                f"Action Required: Inspect upstream logs and consider pool toggle"
            )
            send_slack_alert(message)
            print(f"[ALERT] High error rate: {error_rate:.2f}% ({errors}/{total})")

   
    if pool and pool != last_pool:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        message = (
            f"⚠️ *Failover Detected!*\n"
            f"Previous Pool: `{last_pool}` → Current Pool: `{pool}`\n"
            f"Release: `{release}` | Upstream: `{upstream}` | Upstream Status: `{upstream_status}`\n"
            f"Timestamp: {timestamp}\n"
            f"Action Required: Check health of primary container"
        )
        send_slack_alert(message)
        print(f"[ALERT] Failover detected: {last_pool} → {pool}")
        last_pool = pool


# === Main Runner ===
def main():
    print("Log watcher active — monitoring Nginx structured logs...")
    print(f" Active pool: {ACTIVE_POOL}, Error Threshold: {ERROR_RATE_THRESHOLD}%")
    for line in tail_f(LOG_FILE):
        analyze_log_entry(line)


if __name__ == "__main__":
    main()
