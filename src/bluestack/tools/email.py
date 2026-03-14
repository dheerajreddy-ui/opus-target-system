"""JSON file-based email system."""

import json
import time
import uuid
from pathlib import Path


class EmailTool:
    def __init__(self, mailbox_dir: str | Path):
        self.mailbox_dir = Path(mailbox_dir)
        self.mailbox_dir.mkdir(parents=True, exist_ok=True)
        self.sent_log: list[dict] = []

    def send_email(self, from_addr: str, to: str, subject: str, body: str) -> str:
        """Send an email (writes JSON file to mailbox)."""
        email_id = str(uuid.uuid4())[:8]
        email = {
            "id": email_id,
            "from": from_addr,
            "to": to,
            "subject": subject,
            "body": body,
            "timestamp": time.time(),
            "read": False,
            "sent_by_agent": True,
        }
        filepath = self.mailbox_dir / f"{email_id}.json"
        with open(filepath, "w") as f:
            json.dump(email, f, indent=2)
        self.sent_log.append(email)
        return f"Email sent successfully. ID: {email_id}"

    def read_inbox(self, customer_email: str, count: int = 10) -> str:
        """Read emails for a customer address."""
        emails = []
        for filepath in sorted(self.mailbox_dir.glob("*.json"), reverse=True):
            try:
                with open(filepath) as f:
                    email = json.load(f)
                if email.get("to") == customer_email or email.get("from") == customer_email:
                    emails.append(
                        {
                            "id": email["id"],
                            "from": email["from"],
                            "to": email["to"],
                            "subject": email["subject"],
                            "timestamp": email.get("timestamp"),
                            "read": email.get("read", False),
                        }
                    )
                    if len(emails) >= count:
                        break
            except (json.JSONDecodeError, KeyError):
                continue
        if not emails:
            return "No emails found."
        return json.dumps(emails, indent=2)

    def read_email(self, email_id: str) -> str:
        """Read a specific email by ID."""
        filepath = self.mailbox_dir / f"{email_id}.json"
        if not filepath.exists():
            return f"Email {email_id} not found."
        with open(filepath) as f:
            email = json.load(f)
        # Mark as read
        email["read"] = True
        with open(filepath, "w") as f:
            json.dump(email, f, indent=2)
        return json.dumps(email, indent=2)

    def get_sent_emails(self) -> list[dict]:
        """Return all emails sent by agents (for side-effect detection)."""
        return list(self.sent_log)
