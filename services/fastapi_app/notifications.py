import os
import smtplib
from email.mime.text import MIMEText
import urllib.request
import json

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.mailtrap.io")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 2525))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "alerts@supplychain.ai")

def send_slack_alert(message: str):
    """Send alert message to Slack channel."""
    if not SLACK_WEBHOOK_URL:
        print(f"[Mock Slack Alert] {message}")
        return True
        
    payload = {"text": message}
    try:
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req) as response:
            return response.status == 200
    except Exception as e:
        print(f"Failed to send Slack alert: {e}")
        return False

def send_teams_alert(message: str):
    """Send alert message to Microsoft Teams channel."""
    if not TEAMS_WEBHOOK_URL:
        print(f"[Mock Teams Alert] {message}")
        return True
        
    payload = {"text": message}
    try:
        req = urllib.request.Request(
            TEAMS_WEBHOOK_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req) as response:
            return response.status == 200
    except Exception as e:
        print(f"Failed to send Teams alert: {e}")
        return False

def send_email_alert(recipient: str, subject: str, body: str):
    """Send standard email alert."""
    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"[Mock Email Alert] To: {recipient}, Subject: {subject}, Body: {body}")
        return True
        
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = recipient
    
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SENDER_EMAIL, [recipient], msg.as_string())
        return True
    except Exception as e:
        print(f"Failed to send email alert: {e}")
        return False

def send_sms_alert(phone_number: str, message: str):
    """Send Twilio SMS alert."""
    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    twilio_auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    twilio_number = os.environ.get("TWILIO_NUMBER")
    
    if not twilio_sid or not twilio_auth_token or not twilio_number:
        print(f"[Mock SMS Alert] To: {phone_number}, Msg: {message}")
        return True
        
    # Standard Twilio REST API request using urllib
    import base64
    url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
    auth_str = f"{twilio_sid}:{twilio_auth_token}"
    auth_header = "Basic " + base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
    
    data = urllib.parse.urlencode({
        "To": phone_number,
        "From": twilio_number,
        "Body": message
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": auth_header,
                "Content-Type": "application/x-www-form-urlencoded"
            },
            method="POST"
        )
        with urllib.request.urlopen(req) as response:
            return response.status == 201
    except Exception as e:
        print(f"Failed to send SMS alert: {e}")
        return False

def trigger_all_notifications(supplier_name: str, risk_score: float):
    """Helper to broadcast disruption alerts across all enabled channels."""
    msg = f"CRITICAL: Supplier '{supplier_name}' has reached a critical risk score of {risk_score:.2f}. Triage initiated."
    send_slack_alert(msg)
    send_teams_alert(msg)
    # Mock/Default recipients if not set in configs
    send_email_alert("operations@company.com", "Supply Chain Disruption Alert", msg)
    send_sms_alert("+1234567890", msg)
