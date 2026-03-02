"""SMTP ve uygulama ayarları - .env dosyasından okunur."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .exceptions import ConfigError

# Proje kök dizini (mailbot paketinin bir üst dizini)
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


@dataclass
class SMTPConfig:
    """SMTP yapılandırması — tip güvenli erişim."""

    host: str
    port: int
    user: str
    password: str
    from_addr: str
    use_tls: bool
    reply_to: str | None = None
    cc: list[str] | None = None
    bcc: list[str] | None = None

    def is_configured(self) -> bool:
        """SMTP kimlik bilgileri tanımlı mı?"""
        return bool(self.user and self.password)

    def to_dict(self) -> dict:
        """Eski dict API uyumluluğu için."""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "from_addr": self.from_addr,
            "use_tls": self.use_tls,
            "reply_to": self.reply_to,
            "cc": self.cc,
            "bcc": self.bcc,
        }


def get_smtp_config() -> SMTPConfig:
    """SMTP ayarlarını döndür."""
    port = os.getenv("SMTP_PORT", "587")
    try:
        port = int(port)
    except ValueError:
        port = 587

    def _parse_emails(val: str) -> list[str] | None:
        lst = [e.strip() for e in (val or "").split(",") if e.strip()]
        return lst if lst else None

    return SMTPConfig(
        host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        port=port,
        user=(os.getenv("SMTP_USER") or "").strip(),
        password=(os.getenv("SMTP_PASS") or "").strip(),
        from_addr=(os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or "").strip(),
        use_tls=os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes"),
        reply_to=(os.getenv("REPLY_TO") or "").strip() or None,
        cc=_parse_emails(os.getenv("CC") or ""),
        bcc=_parse_emails(os.getenv("BCC") or ""),
    )


def validate_smtp_config(config: SMTPConfig, *, require_credentials: bool = True) -> None:
    """SMTP yapılandırmasını doğrular. Hata varsa ConfigError fırlatır."""
    if not config.host:
        raise ConfigError("SMTP_HOST tanımlı olmalı.")
    if config.port < 1 or config.port > 65535:
        raise ConfigError(f"SMTP_PORT geçersiz: {config.port}")
    if require_credentials and not config.is_configured():
        raise ConfigError(
            "SMTP_USER ve SMTP_PASS tanımlı olmalı.",
            details=".env dosyasında SMTP bilgilerini kontrol edin.",
        )


def get_attachments() -> list[str]:
    """Ek dosyalar - .env ATTACHMENTS (virgülle ayrılmış)."""
    val = os.getenv("ATTACHMENTS", "")
    if not val:
        return []
    return [p.strip() for p in val.split(",") if p.strip()]


def get_sender_name() -> str:
    """İmza için gönderen adı - .env SENDER_NAME veya SMTP_FROM'dan."""
    name = os.getenv("SENDER_NAME", "")
    if name:
        return name
    addr = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER", "")
    if "@" in addr:
        return addr.split("@")[0].replace(".", " ").title()
    return "Mail Bot"


def get_sender_phone() -> str:
    """İmza için gönderen telefonu - .env SENDER_PHONE."""
    return (os.getenv("SENDER_PHONE") or "").strip()


def get_sender_email() -> str:
    """İmza için gönderen e-posta - .env SENDER_EMAIL veya SMTP_FROM."""
    email = (os.getenv("SENDER_EMAIL") or "").strip()
    if email:
        return email
    return (os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or "").strip()


def get_sender_linkedin() -> str:
    """İmza için gönderen LinkedIn - .env SENDER_LINKEDIN."""
    return (os.getenv("SENDER_LINKEDIN") or "").strip()


def get_sender_linkedin_label() -> str:
    """LinkedIn linkinde görünecek kısa metin - .env SENDER_LINKEDIN_LABEL. Yoksa URL gösterilir."""
    return (os.getenv("SENDER_LINKEDIN_LABEL") or "").strip()


def get_sender_website() -> str:
    """İmza için sosyal medya URL - .env SENDER_WEBSITE."""
    return (os.getenv("SENDER_WEBSITE") or "").strip()


def get_sender_social_media_label() -> str:
    """Sosyal medya linkinde görünecek kısa metin - .env SENDER_SOCIAL_MEDIA_LABEL. Yoksa URL gösterilir."""
    return (os.getenv("SENDER_SOCIAL_MEDIA_LABEL") or "").strip()


def get_sender_address() -> str:
    """İmza için adres - .env SENDER_ADDRESS."""
    return (os.getenv("SENDER_ADDRESS") or "").strip()


def get_sender_title() -> str:
    """İmza için unvan - .env SENDER_TITLE."""
    return (os.getenv("SENDER_TITLE") or "Komite Üyesi").strip()


def get_vizyon_canva_link() -> str:
    """AIS vizyon sunumu Canva linki - .env VIZYON_CANVA_LINK."""
    return (os.getenv("VIZYON_CANVA_LINK") or "").strip()


def get_sender_logo_url() -> str:
    """İmza logosu - .env SENDER_LOGO_URL. Harici URL kullanın (base64 e-posta istemcilerinde sorun çıkarır)."""
    return (os.getenv("SENDER_LOGO_URL") or "").strip()


def get_send_delay() -> int:
    """Her mail arası bekleme süresi (saniye) - .env SEND_DELAY."""
    val = os.getenv("SEND_DELAY", "0")
    try:
        return max(0, int(val))
    except ValueError:
        return 0


def get_send_at() -> str | None:
    """Zamanlanmış gönderim için .env'deki SEND_AT değerini döndür."""
    return os.getenv("SEND_AT") or None


def get_paths() -> dict:
    """Dosya yollarını döndür."""
    return {
        "alicilar": ROOT_DIR / "alicilar.txt",
        "templates": ROOT_DIR / "templates",
        "subject": ROOT_DIR / "templates" / "subject.txt",
        "body_txt": ROOT_DIR / "templates" / "body.txt",
        "body_html": ROOT_DIR / "templates" / "body.html",
        "signature_txt": ROOT_DIR / "templates" / "signature.txt",
        "signature_html": ROOT_DIR / "templates" / "signature.html",
    }
