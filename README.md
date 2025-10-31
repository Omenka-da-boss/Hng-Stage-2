# 🧠 Nginx Blue-Green Failover Alert System

This project implements a **Blue-Green Deployment Monitoring and Alert System** using **Nginx**, a **Python-based Log Watcher**, and **Slack integration** for automated alerts.

---

## 🚀 Overview

The setup provides:
- Extended **Nginx access logs** with custom fields (`pool`, `release`, `upstream_status`, `upstream_addr`, `request_time`, etc.)
- A **log watcher service** that tails Nginx logs in real time
- Slack alerts for:
  - Failover events (e.g., blue → green)
  - High error rate (>2% 5xx over last 200 requests)
- A **Runbook** for handling alerts and recovery

---

## 🧩 Project Structure

```
├── docker-compose.yml
├── nginx.conf
├── watcher.py
├── requirements.txt
├── .env
├── runbook.md
└── README.md
```

---

## ⚙️ Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/<your-repo>/nginx-alert-watcher.git
cd nginx-alert-watcher
```

### 2. Create and Configure `.env`
```env
BLUE_IMAGE=yimikaade/wonderful:devops-stage-two
GREEN_IMAGE=yimikaade/wonderful:devops-stage-two
ACTIVE_POOL=blue
ERROR_RATE_THRESHOLD=2
WINDOW_SIZE=200
ALERT_COOLDOWN_SEC=300
RELEASE_ID_BLUE=blue-v1
RELEASE_ID_GREEN=green-v1
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXXX/YYYY/ZZZZ
```

### 3. Install Dependencies (for watcher)
If running watcher locally:
```bash
pip install -r requirements.txt
```

### 4. Start All Services
```bash
docker compose up -d
```
This will launch:
- `app_blue` and `app_green`
- `nginx` for load balancing
- `alert_watcher` for monitoring logs and sending Slack alerts

---

## 🧪 Chaos Testing & Verification

### **1️⃣ Trigger Failover (Blue → Green)**
Simulate downtime for Blue:
```bash
curl -X POST http://localhost:8081/chaos/start
```
Expected:
- Nginx switches traffic to Green.
- Slack alert: **Failover Detected** (Blue → Green).

---

### **2️⃣ Simulate High Error Rate**
Send requests that cause server errors:
```bash
ab -n 200 -c 10 http://localhost:8080/fail
```
Expected:
- Slack alert: **High Error Rate Detected**
- Message includes window size, rate, and timestamp.

---

### **3️⃣ Recovery Test**
Once Blue recovers:
```bash
curl -X POST http://localhost:8081/chaos/stop
```
Expected:
- Slack alert: **Recovery Detected — Primary Restored**

---

## 🔍 Viewing Logs

### **Nginx Logs**
```bash
docker logs nginx
```
You’ll see structured log lines such as:
```
pool=blue release=blue-v1 upstream_status=200 upstream_addr=172.18.0.3:3000 request_time=0.123
```

### **Watcher Logs**
```bash
docker logs alert_watcher
```
Shows:
- Real-time monitoring messages  
- Detected failovers  
- Error-rate alerts  
- Slack delivery confirmation

---

## 💬 Slack Alert Examples

| Event Type | Screenshot Reference | Description |
|-------------|----------------------|--------------|
| **Failover Detected** | `./screenshots/failover_alert.png` | Triggered when Nginx switches from Blue → Green |
| **High Error Rate** | `./screenshots/error_rate_alert.png` | When error rate exceeds 2% over last 200 requests |
| **Nginx Log Output** | `./screenshots/nginx_log_snippet.png` | Shows extended log fields with pool/release info |

---

## 📘 Runbook

Refer to [`runbook.md`](./runbook.md) for:
- Meaning of each alert
- Recovery actions
- Maintenance mode (alert suppression)
- Troubleshooting steps

---

## ✅ Acceptance Criteria Checklist

- [x] Nginx logs show `pool`, `release`, `upstream status`, and address  
- [x] Watcher posts Slack alerts for failover and error-rate breaches  
- [x] Alerts are deduplicated and rate-limited  
- [x] Runbook is included and operator-friendly  
- [x] Chaos drill triggers Slack failover alert  
- [x] Error simulation triggers high error-rate alert  

---

## 🧰 Useful Commands

| Purpose | Command |
|----------|----------|
| View all containers | `docker ps` |
| Tail watcher logs | `docker logs -f alert_watcher` |
| Stop everything | `docker compose down` |
| Rebuild all | `docker compose up --build -d` |

---

## 🧠 Author
**Omenka Ndubuisi David**  
📧 omenkan…@gmail.com  
🐙 [GitHub](https://github.com/Omenka-da-boss)

