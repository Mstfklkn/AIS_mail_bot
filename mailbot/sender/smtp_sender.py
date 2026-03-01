"""SMTP ile mail gönderimi (587 STARTTLS / 465 SSL)."""

import mimetypes
import smtplib
import time
from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from ..constants import MAX_ATTACHMENT_SIZE, MAX_TOTAL_ATTACHMENT_SIZE
from ..constants import SMTP_MAX_RETRIES, SMTP_RETRY_DELAY_SEC
from ..models import EmailMessage, Recipient
from ..exceptions import SendError


def check_attachment_sizes(file_paths: list[str]) -> None:
    """Ek dosyaların toplam boyutunu kontrol eder. Limit aşımında SendError."""
    total = 0
    for fp in file_paths:
        path = Path(fp)
        if path.exists():
            size = path.stat().st_size
            total += size
            if size > MAX_ATTACHMENT_SIZE:
                raise SendError(f"Ek dosya çok büyük: {path.name} (max 25 MB)")
    if total > MAX_TOTAL_ATTACHMENT_SIZE:
        raise SendError(f"Toplam ek boyutu çok büyük: {total / 1024 / 1024:.1f} MB (max 25 MB)")


def _attach_file(msg: MIMEMultipart, file_path: str) -> None:
    """Dosyayı mesaja ekler."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Ek dosya bulunamadı: {path}")
    size = path.stat().st_size
    if size > MAX_ATTACHMENT_SIZE:
        raise SendError(f"Ek dosya çok büyük: {path.name} ({size / 1024 / 1024:.1f} MB, max 25 MB)")

    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type is None:
        mime_type = "application/octet-stream"

    main_type, sub_type = mime_type.split("/", 1)
    with path.open("rb") as f:
        part = MIMEBase(main_type, sub_type)
        part.set_payload(f.read())
    encode_base64(part)
    part.add_header("Content-Disposition", "attachment", filename=path.name)
    msg.attach(part)


def _do_send(server: smtplib.SMTP | smtplib.SMTP_SSL, from_addr: str, recipients: list[str], msg_str: str) -> None:
    """Tek gönderim denemesi. Hata durumunda exception fırlatır."""
    server.sendmail(from_addr, recipients, msg_str)


def send_email(
    message: EmailMessage,
    recipient: Recipient,
    smtp_config: dict,
    *,
    max_retries: int = SMTP_MAX_RETRIES,
) -> None:
    """
    SMTP ile mail gönderir. Geçici hatalarda yeniden dener.
    - Port 587: STARTTLS
    - Port 465: SSL
    - Ek dosyalar desteklenir
    """
    has_attachments = message.attachments and len(message.attachments) > 0

    if has_attachments:
        msg = MIMEMultipart("mixed")
    else:
        msg = MIMEMultipart("alternative")

    msg["Subject"] = message.subject
    msg["From"] = message.from_addr or smtp_config["from_addr"]
    msg["To"] = recipient.email

    if message.reply_to or smtp_config.get("reply_to"):
        msg["Reply-To"] = message.reply_to or smtp_config.get("reply_to")
    cc_list = message.cc or smtp_config.get("cc") or []
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    bcc_list = message.bcc or smtp_config.get("bcc") or []
    if bcc_list:
        msg["Bcc"] = ", ".join(bcc_list)

    # Metin içeriği
    if has_attachments:
        body_part = MIMEMultipart("alternative")
        body_part.attach(MIMEText(message.body_text, "plain", "utf-8"))
        if message.body_html:
            body_part.attach(MIMEText(message.body_html, "html", "utf-8"))
        msg.attach(body_part)
    else:
        msg.attach(MIMEText(message.body_text, "plain", "utf-8"))
        if message.body_html:
            msg.attach(MIMEText(message.body_html, "html", "utf-8"))

    # Ek dosyalar
    for file_path in message.attachments or []:
        _attach_file(msg, file_path)

    host = smtp_config["host"]
    port = smtp_config["port"]
    user = smtp_config["user"]
    password = smtp_config["password"]
    use_tls = smtp_config["use_tls"]

    # Tüm alıcılar (To + Cc + Bcc)
    all_recipients = [recipient.email]
    if msg.get("Cc"):
        all_recipients.extend([e.strip() for e in msg["Cc"].split(",") if e.strip()])
    if msg.get("Bcc"):
        all_recipients.extend([e.strip() for e in msg["Bcc"].split(",") if e.strip()])

    from_addr = msg["From"]
    msg_str = msg.as_string()
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            if port == 465:
                with smtplib.SMTP_SSL(host, port) as server:
                    server.login(user, password)
                    _do_send(server, from_addr, all_recipients, msg_str)
            else:
                with smtplib.SMTP(host, port) as server:
                    if use_tls:
                        server.starttls()
                    server.login(user, password)
                    _do_send(server, from_addr, all_recipients, msg_str)
            return
        except (smtplib.SMTPException, OSError) as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = SMTP_RETRY_DELAY_SEC * (2**attempt)
                time.sleep(delay)

    raise SendError(str(last_error), details=f"SMTP sunucusu: {host}:{port}")
