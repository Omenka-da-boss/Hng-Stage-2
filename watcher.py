#!/usr/bin/env python3
import os
import time
import re
import json
import requests
from collections import deque
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LogWatcher:
    def __init__(self):
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        self.error_threshold = float(os.getenv('ERROR_RATE_THRESHOLD', 2.0))
        self.window_size = int(os.getenv('WINDOW_SIZE', 200))
        self.cooldown_sec = int(os.getenv('ALERT_COOLDOWN_SEC', 300))
        self.maintenance_mode = os.getenv('MAINTENANCE_MODE', 'false').lower() == 'true'
        
        # State tracking
        self.last_pool = None
        self.last_alert_time = {}
        self.request_window = deque(maxlen=self.window_size)
        self.current_pool = None
        
        # Log pattern matching
        self.log_pattern = re.compile(
            r'\[(?P<timestamp>.*?)\] '
            r'(?P<remote_addr>\S+) '
            r'"(?P<request>.*?)" '
            r'(?P<status>\d+) '
            r'"(?P<user_agent>.*?)" '
            r'(?P<request_time>\S+) '
            r'(?P<upstream_response_time>\S+) '
            r'"(?P<upstream_addr>.*?)" '
            r'(?P<upstream_status>\S+) '
            r'"(?P<pool>.*?)" '
            r'"(?P<release>.*?)"'
        )
        
        logger.info(f"LogWatcher initialized: threshold={self.error_threshold}%, "
                   f"window={self.window_size}, cooldown={self.cooldown_sec}s, "
                   f"maintenance_mode={self.maintenance_mode}")

    def parse_log_line(self, line):
        """Parse a single log line and extract structured data"""
        match = self.log_pattern.match(line)
        if not match:
            return None
            
        data = match.groupdict()
        
        # Convert numeric fields
        try:
            data['status'] = int(data['status'])
            data['request_time'] = float(data['request_time']) if data['request_time'] != '-' else 0.0
            data['upstream_response_time'] = float(data['upstream_response_time']) if data['upstream_response_time'] != '-' else 0.0
            data['upstream_status'] = int(data['upstream_status']) if data['upstream_status'] != '-' else data['status']
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing numeric fields: {e}")
            return None
            
        return data

    def calculate_error_rate(self):
        """Calculate current error rate in the window"""
        if not self.request_window:
            return 0.0
            
        error_count = sum(1 for req in self.request_window 
                         if 500 <= req.get('upstream_status', 0) < 600)
        return (error_count / len(self.request_window)) * 100

    def is_cooldown_active(self, alert_type):
        """Check if we're in cooldown period for an alert type"""
        if alert_type not in self.last_alert_time:
            return False
            
        elapsed = time.time() - self.last_alert_time[alert_type]
        return elapsed < self.cooldown_sec

    def send_slack_alert(self, alert_type, message, details=None):
        """Send alert to Slack"""
        if self.maintenance_mode:
            logger.info(f"Maintenance mode: suppressing {alert_type} alert")
            return
            
        if not self.slack_webhook:
            logger.error("SLACK_WEBHOOK_URL not configured")
            return
            
        if self.is_cooldown_active(alert_type):
            logger.info(f"Cooldown active for {alert_type}, suppressing alert")
            return

        payload = {
            "text": f"🚨 *{alert_type}*",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🚨 *{alert_type}*\n{message}"
                    }
                }
            ]
        }

        if details:
            details_text = "\n".join([f"• {k}: {v}" for k, v in details.items()])
            payload["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Details:*\n{details_text}"
                }
            })

        try:
            response = requests.post(
                self.slack_webhook,
                json=payload,
                timeout=10
            )
            if response.status_code == 200:
                logger.info(f"Slack alert sent: {alert_type}")
                self.last_alert_time[alert_type] = time.time()
            else:
                logger.error(f"Slack API error: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

    def process_log_line(self, line):
        """Process a single log line and trigger alerts if needed"""
        data = self.parse_log_line(line)
        if not data:
            return

        # Add to request window for error rate calculation
        self.request_window.append(data)

        # Check for pool changes (failover detection)
        current_pool = data.get('pool')
        if current_pool and current_pool != self.current_pool:
            if self.current_pool and current_pool != self.current_pool:
                # Failover detected
                alert_msg = f"Traffic switched from *{self.current_pool}* to *{current_pool}*"
                details = {
                    "Previous Pool": self.current_pool,
                    "New Pool": current_pool,
                    "Release": data.get('release', 'unknown'),
                    "Timestamp": data.get('timestamp', 'unknown')
                }
                self.send_slack_alert("Failover Detected", alert_msg, details)
            
            self.current_pool = current_pool

        # Check error rate
        error_rate = self.calculate_error_rate()
        if error_rate > self.error_threshold and len(self.request_window) >= self.window_size:
            alert_msg = f"Error rate {error_rate:.1f}% exceeds threshold {self.error_threshold}%"
            details = {
                "Current Error Rate": f"{error_rate:.1f}%",
                "Threshold": f"{self.error_threshold}%",
                "Window Size": len(self.request_window),
                "Active Pool": self.current_pool or 'unknown'
            }
            self.send_slack_alert("High Error Rate", alert_msg, details)

    def watch_logs(self, log_file_path='/var/log/nginx/access.log'):
        """Main loop to watch and process log files"""
        logger.info(f"Starting to watch log file: {log_file_path}")
        
        # Wait for log file to be created
        while not os.path.exists(log_file_path):
            logger.info(f"Waiting for log file: {log_file_path}")
            time.sleep(2)

        # Start from the end of the file
        with open(log_file_path, 'r') as file:
            file.seek(0, 2)  # Go to end of file
            
            while True:
                line = file.readline()
                if line:
                    try:
                        self.process_log_line(line.strip())
                    except Exception as e:
                        logger.error(f"Error processing log line: {e}")
                else:
                    time.sleep(0.1)  # Small delay when no new lines

if __name__ == '__main__':
    watcher = LogWatcher()
    watcher.watch_logs()
