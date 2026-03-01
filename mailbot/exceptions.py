"""Özel istisna sınıfları."""


class MailBotError(Exception):
    """Mail Bot temel istisna sınıfı."""

    def __init__(self, message: str, details: str | None = None):
        self.message = message
        self.details = details
        super().__init__(message)


class ConfigError(MailBotError):
    """Yapılandırma hatası (.env, SMTP vb.)."""


class ValidationError(MailBotError):
    """Doğrulama hatası (e-posta, alıcı listesi vb.)."""


class TemplateError(MailBotError):
    """Şablon render hatası (Jinja2)."""


class SendError(MailBotError):
    """Mail gönderim hatası (SMTP)."""
