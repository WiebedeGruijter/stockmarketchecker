"""Notification backends for huurwatcher."""
from __future__ import annotations

import os
import smtplib
import subprocess
import urllib.parse
import urllib.request
from email.message import EmailMessage


def notify_mac(title: str, message: str, url: str | None = None) -> None:
    """Native macOS notification via osascript. Clicking it won't open the
    URL (macOS notifications don't support that without extra tooling), so
    we just put the URL in the message body."""
    body = message if not url else f"{message}\n{url}"
    script = (
        f'display notification "{_escape(body)}" '
        f'with title "{_escape(title)}"'
    )
    subprocess.run(["osascript", "-e", script], check=False)


def notify_telegram(bot_token: str, chat_id: str, title: str, message: str, url: str | None = None) -> None:
    if not bot_token or not chat_id:
        return
    text = f"*{title}*\n{message}"
    if url:
        text += f"\n{url}"
    api = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(api, data=data), timeout=10)
    except Exception as exc:  # pragma: no cover - best effort
        print(f"[notify] Telegram send failed: {exc}")


def notify_email(host: str, port: int, username: str, password: str, sender: str, recipient: str, title: str, message: str, url: str | None = None) -> None:
    password = password or os.getenv("GOOGLEPASSKEY", "")
    sender = sender or os.getenv("EMAIL_FROM", "")
    recipient = recipient or os.getenv("EMAIL_TO", "")
    if not host or not username or not password or not sender or not recipient:
        return
    msg = EmailMessage()
    msg["Subject"] = title
    msg["From"] = sender
    msg["To"] = recipient
    body = message if not url else f"{message}\n\n{url}"
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
    except Exception as exc:  # pragma: no cover - best effort
        print(f"[notify] Email send failed: {exc}")


def _escape(text: str) -> str:
    return text.replace('"', '\\"').replace("\n", " ")


def send(channels: list[str], config: dict, title: str, message: str, url: str | None = None) -> None:
    if "mac" in channels:
        notify_mac(title, message, url)
    if "telegram" in channels:
        tg = config.get("telegram", {})
        notify_telegram(tg.get("bot_token", ""), tg.get("chat_id", ""), title, message, url)
    if "email" in channels:
        email_cfg = config.get("email", {})
        notify_email(
            email_cfg.get("host", ""),
            int(email_cfg.get("port", 587)),
            email_cfg.get("username", ""),
            email_cfg.get("password", ""),
            email_cfg.get("from_address", ""),
            email_cfg.get("to_address", ""),
            title,
            message,
            url,
        )
