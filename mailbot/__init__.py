"""Mail Bot - Şablon tabanlı toplu mail gönderimi."""

from .exceptions import ConfigError, MailBotError, SendError, TemplateError, ValidationError

__all__ = [
    "ConfigError",
    "MailBotError",
    "SendError",
    "TemplateError",
    "ValidationError",
]
