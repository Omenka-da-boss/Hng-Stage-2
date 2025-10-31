#  **Nginx Log Watcher Runbook**

##  Overview

This runbook explains how to interpret alerts from the **Nginx Log Watcher** system and the correct operator actions to take.
The watcher continuously monitors structured Nginx access logs, detects **failover** and **error-rate anomalies**, and sends alerts to Slack.

---

## ⚙️ **System Context**

| Component         | Description                                                                                                                             |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Nginx**         | Acts as reverse proxy for Blue/Green applications (`app_blue` and `app_green`). Logs contain `pool`, `release`, and `upstream` details. |
| **Alert Watcher** | A Python service that tails Nginx logs, parses pool/error data, and posts alerts to Slack using the webhook URL from `.env`.            |
| **Slack Alerts**  | Used to notify operators of pool changes (failover), high error rates, or recovery events.                                              |
| **Shared Volume** | `/var/log/nginx` mounted between Nginx and watcher for real-time log access.                                                            |

---

##  **Alert Types and Actions**

###  **Failover Detected**

**Description:**
Triggered when Nginx switches traffic from one pool to another (e.g., `blue → green`).
This typically happens because one upstream app became unresponsive or returned consecutive 5xx errors.

**Slack Message Example:**

```
 *Failover Detected!*
Previous Pool: `blue` → Current Pool: `green`
Release: `green-v1`
Timestamp: 2025-10-31 10:22:16 UTC
Action Required: Check health of primary container
```

**Operator Actions:**

1. Verify the failing pool container:

   ```bash
   docker ps -a | grep app_blue
   docker logs app_blue | tail -n 20
   ```
2. Check for crash loops, port binding issues, or 5xx responses.
3. Restart or redeploy the affected container:

   ```bash
   docker restart app_blue
   ```
4. Once recovered, traffic will automatically return to the healthy pool.

---

###  **High Error Rate Detected**

**Description:**
Triggered when the rate of 5xx responses exceeds the configured threshold (e.g., >2% of last 200 requests).
This indicates partial upstream instability — possibly high latency, backend exceptions, or temporary overload.

**Slack Message Example:**

```
 *High Error Rate Detected*
Error Rate: *98.59%*
Window: *70/71 requests*
Timestamp: 2025-10-31 02:35:06 UTC
Action Required: Inspect upstream logs and consider pool toggle
```

**Operator Actions:**

1. Inspect Nginx and upstream logs:

   ```bash
   docker exec -it nginx tail -n 50 /var/log/nginx/access.log
   docker logs app_blue | tail -n 50
   docker logs app_green | tail -n 50
   ```
2. Identify the source of the errors (e.g., database connectivity, app crash, timeout).
3. If sustained, perform a **manual pool switch** by updating `ACTIVE_POOL` in `.env` and reloading Nginx.
4. Notify team if system remains degraded beyond recovery time threshold.

---

###  **Recovery Detected**

**Description:**
Triggered when the previously failed pool resumes serving healthy (2xx) responses and becomes active again.

**Slack Message Example:**

```
 *Recovery Detected!*
Primary pool `blue` is serving traffic again.
Timestamp: 2025-10-31 10:40:12 UTC
Action: Resume normal monitoring.
```

**Operator Actions:**

1. Confirm recovery in logs:

   ```bash
   docker logs -f nginx | grep blue
   ```
2. Ensure error rate has dropped below threshold.
3. Document the incident and cause in your operations log.

---

## 🧮 **Maintenance Mode (Suppressing Alerts)**

During planned upgrades or toggles, operators can **suppress alerts** to prevent Slack spam.

**How to Enable Maintenance Mode:**

1. In `.env`, set:

   ```env
   MAINTENANCE_MODE=true
   ```
2. Restart the watcher service:

   ```bash
   docker restart alert_watcher
   ```
3. Perform your deployment or testing.
4. Once done, re-enable alerts:

   ```bash
   MAINTENANCE_MODE=false
   docker restart alert_watcher
   ```

The watcher will log:

```
[INFO] Maintenance mode enabled — suppressing alerts.
```

---

## ⚙️ **Configuration Parameters**

| Variable               | Description                             | Default |
| ---------------------- | --------------------------------------- | ------- |
| `SLACK_WEBHOOK_URL`    | Slack Incoming Webhook URL              | —       |
| `ACTIVE_POOL`          | Initial active pool (`blue` or `green`) | blue    |
| `ERROR_RATE_THRESHOLD` | % of 5xx responses that triggers alert  | 2       |
| `WINDOW_SIZE`          | Number of recent requests to track      | 200     |
| `ALERT_COOLDOWN_SEC`   | Cooldown between alerts (in seconds)    | 300     |
| `MAINTENANCE_MODE`     | Suppresses alerts when `true`           | false   |

---

##  **Validation Checklist**

| Test                | Expected Outcome                          |
| ------------------- | ----------------------------------------- |
| Failover Simulation | “ Failover Detected” Slack alert        |
| Error Injection     | “ High Error Rate Detected” Slack alert |
| Recovery            | “ Recovery Detected” Slack alert         |
| Maintenance Mode    | No Slack alerts during maintenance        |

---

##  **Operator Quick Commands**

```bash
# Tail watcher logs
docker logs -f alert_watcher

# Tail Nginx logs
docker exec -it nginx tail -n 20 /var/log/nginx/access.log

# Force failover
docker stop app_blue

# Simulate high error rate
curl -X POST http://localhost:8080/chaos/start
```

---

##  **Summary**

* **Failover Detected →** check failing app container.
* **High Error Rate →** review upstream and Nginx logs.
* **Recovery →** system stabilized, resume monitoring.
* **Maintenance Mode →** temporarily suppress alerts for upgrades.
