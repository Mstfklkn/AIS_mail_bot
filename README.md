# Mail Bot

Şablon tabanlı toplu mail gönderim botu. `alicilar.txt` ve `templates/` ile basit yapılandırma.

## Kurulum

```bash
# Bağımlılıkları yükle
pip install -r requirements.txt

# Yapılandırma dosyalarını oluştur
cp .env.example .env
cp alicilar.txt.example alicilar.txt

# .env ve alicilar.txt dosyalarını düzenleyin
```

## Yapılandırma

1. `.env` dosyasını düzenleyin (`.env.example` kopyalandıysa):
   - **SMTP:** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`
   - **Opsiyonel:** `REPLY_TO`, `CC`, `BCC` (virgülle ayrılmış)

2. `alicilar.txt` — Her satır: `email/kişi_adı/şirket` (e-posta formatı otomatik kontrol edilir)

3. `templates/subject.txt` ve `templates/body.txt` — Jinja2 şablonları:
   - `{{ name }}`, `{{ company }}`, `{{ email }}`

4. `templates/signature.txt` ve `templates/signature.html` — Mail imzası (varsa body sonuna eklenir). `.env` ile `SENDER_NAME`, `SENDER_TITLE`, `SENDER_PHONE`, `SENDER_EMAIL`, `SENDER_WEBSITE`, `SENDER_LINKEDIN`, `SENDER_ADDRESS` tanımlayın. Logo: `SENDER_LOGO_URL` (harici URL, base64 e-posta istemcilerinde sorun çıkarır).

## Kullanım

```bash
# Proje yapısını oluştur (ilk kurulumda)
python -m mailbot init

# Mailleri hemen gönder
python -m mailbot send

# Belirli bir saatte gönder (sistem zamanlayıcısına kaydedilir, PC kapatılsa bile çalışır)
python -m mailbot send --at "2025-02-28 14:30"
python -m mailbot send --at "28.02.2025 14:30"
python -m mailbot send --at "14:30"   # Bugün 14:30'da

# İnteraktif menü (terminalde zaman seç)
python -m mailbot send
# → 1) Hemen  2) Bugün saat X  3) Belirli tarih

# Soru sormadan hemen gönder (script için)
python -m mailbot send -y

# Önizleme — göndermeden konu ve içeriği göster
python -m mailbot send --dry-run

# Her mail arası bekleme (zamanlanmış gönderimde de saat geldikten sonra uygulanır)
python -m mailbot send --delay 2

# Ek dosyalarla gönder (birden fazla -a, toplam max 25 MB)
python -m mailbot send -a brosur.pdf -a fiyat-listesi.xlsx

# Başarısız alıcılara tekrar gönder (failed.txt'den)
python -m mailbot send --retry-failed
```

**Ek dosyalar** `.env` ile: `ATTACHMENTS=ek1.pdf,ek2.pdf`

İnteraktif modda (`python -m mailbot send`) ek dosya sorusu gelir — virgülle ayırarak yolları girin, ek istemiyorsanız `yok` yazın.

Zamanlama `.env` ile: `SEND_AT=2025-02-28 14:30`  
Gecikme `.env` ile: `SEND_DELAY=2`

**Başarısız gönderimler** `failed.txt` dosyasına yazılır. `python -m mailbot send --retry-failed` ile tekrar deneyebilirsiniz.

**Yinelenen alıcılar** otomatik filtrelenir (ilk geçiş tutulur). **Ek boyutu** toplam 25 MB ile sınırlıdır (Gmail).

**Zamanlanmış gönderim:** Sistem zamanlayıcısı kullanılır — macOS: launchd, Linux: at, Windows: Task Scheduler. `mailbot_scheduled.sh` (veya Windows'ta `.bat`) otomatik oluşturulur.

## Mimari

```
alicilar.txt → parse → Recipient
templates/   → Jinja2 → subject + body
.env         → SMTP config
                    ↓
              smtplib ile gönderim
```
