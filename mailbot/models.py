"""Veri modelleri: Recipient ve EmailMessage."""

import re
from dataclasses import dataclass

# E-posta format kontrolü için basit regex (RFC 5322'nin basitleştirilmiş hali)
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def is_valid_email(email: str) -> bool:
    """E-posta adresinin geçerli formatta olup olmadığını kontrol eder."""
    if not email or len(email) > 254:
        return False
    return bool(EMAIL_RE.match(email.strip()))


@dataclass
class Recipient:
    """Alıcı bilgisi - alicilar.txt satırından parse edilir."""

    email: str
    name: str
    company: str

    @classmethod
    def from_line(cls, line: str) -> "Recipient | None":
        """
        Satırdan Recipient oluştur.
        Format: email/kişi_adı/şirket
        Boş satır ve # ile başlayanlar None döner.
        """
        line = line.strip()
        if not line or line.startswith("#"):
            return None

        parts = line.split("/", 2)
        if len(parts) < 3:
            return None

        return cls(
            email=parts[0].strip(),
            name=parts[1].strip(),
            company=parts[2].strip(),
        )

    def to_context(self) -> dict:
        """Jinja2 şablonları için context."""
        return {
            "email": self.email,
            "name": self.name,
            "company": self.company,
        }


@dataclass
class EmailMessage:
    """Gönderilecek mail mesajı."""

    subject: str
    body_text: str
    body_html: str | None = None
    from_addr: str = ""
    to_addr: str = ""
    attachments: list[str] | None = None  # Dosya yolları
    reply_to: str | None = None
    cc: list[str] | None = None
    bcc: list[str] | None = None
