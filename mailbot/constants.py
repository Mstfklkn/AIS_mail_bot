"""Uygulama sabitleri."""

# Ek dosya limitleri (bayt)
MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024  # 25 MB tek dosya
MAX_TOTAL_ATTACHMENT_SIZE = 25 * 1024 * 1024  # 25 MB toplam

# SMTP yeniden deneme
SMTP_MAX_RETRIES = 3
SMTP_RETRY_DELAY_SEC = 2  # İlk bekleme, sonra katlanır

# Zaman formatları (parse_send_time için)
DATE_FORMATS = [
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y %H:%M:%S",
    "%H:%M",
    "%H:%M:%S",
]

# Sadece saat verilmişse kullanılan formatlar (bugünün tarihi eklenir)
TIME_ONLY_FORMATS = ("%H:%M", "%H:%M:%S")

# scheduled.json tarih formatı
SCHEDULED_DATETIME_FMT = "%Y-%m-%dT%H:%M:%S"
