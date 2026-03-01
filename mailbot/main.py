"""CLI: send ve init komutları."""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .config import (
    ROOT_DIR,
    get_attachments,
    get_paths,
    get_send_at,
    get_send_delay,
    get_smtp_config,
    validate_smtp_config,
)
from .constants import DATE_FORMATS, SCHEDULED_DATETIME_FMT, TIME_ONLY_FORMATS
from .exceptions import ConfigError, MailBotError, SendError, TemplateError, ValidationError
from .scheduler import schedule_system
from .models import EmailMessage, Recipient, is_valid_email
from .sender import send_email
from .sender.smtp_sender import check_attachment_sizes
from .templating import build_message
from .ui import accent, banner, dim, error, progress_bar, separator, success, title, warn


def load_recipients(path: Path, deduplicate: bool = True) -> list[Recipient]:
    """Dosyadan alıcıları yükler. deduplicate=True ise yinelenen e-postalar filtrelenir (ilk geçiş tutulur)."""
    if not path.exists():
        raise ValidationError(f"Dosya bulunamadı: {path}")

    recipients = []
    seen_emails: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise ValidationError(f"Dosya okunamadı: {path}", details=str(e))

    for line in lines:
        r = Recipient.from_line(line)
        if r:
            if deduplicate and r.email.lower() in seen_emails:
                continue
            seen_emails.add(r.email.lower())
            recipients.append(r)
    return recipients


def parse_send_time(value: str) -> datetime | None:
    """
    Zaman string'ini datetime'a çevirir.
    Desteklenen formatlar: YYYY-MM-DD HH:MM, DD.MM.YYYY HH:MM, HH:MM
    """
    value = value.strip()
    if not value:
        return None

    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            if fmt in TIME_ONLY_FORMATS:
                now = datetime.now()
                dt = dt.replace(year=now.year, month=now.month, day=now.day)
            return dt
        except ValueError:
            continue
    return None


def wait_until(target: datetime) -> None:
    """Hedef zamana kadar bekler, her dakika durumu yazdırır."""
    import time

    while True:
        now = datetime.now()
        if now >= target:
            break
        diff = (target - now).total_seconds()
        mins = int(diff // 60)
        secs = int(diff % 60)
        msg = dim(f"  ⏳ Bekleniyor... {target.strftime('%d.%m.%Y %H:%M')} ({mins} dk {secs} sn kaldı)")
        print(msg, end="\r")
        time.sleep(min(60, max(1, diff)))
    print(" " * 60, end="\r")


def prompt_send_time() -> str | None:
    """Terminalden interaktif olarak gönderim zamanı alır."""
    print()
    print(title("  ⏰ Gönderim zamanı"))
    print(dim("  ─────────────────────────────"))
    print(f"    {accent('1)')} Hemen gönder")
    print(f"    {accent('2)')} Bugün belirli saatte (örn: 14:30)")
    print(f"    {accent('3)')} Belirli tarih ve saatte (örn: 28.02.2025 14:30)")
    print()

    try:
        choice = input(dim("  Seçiminiz (1/2/3) [1]: ")).strip() or "1"
    except (EOFError, KeyboardInterrupt):
        print(f"\n{warn('İptal edildi.')}")
        sys.exit(0)

    if choice == "1":
        return None

    if choice == "2":
        try:
            t = input(dim("  Saat (HH:MM): ")).strip()
            return t if t else None
        except (EOFError, KeyboardInterrupt):
            print(f"\n{warn('İptal edildi.')}")
            sys.exit(0)

    if choice == "3":
        try:
            t = input(dim("  Tarih ve saat (GG.AA.YYYY HH:MM): ")).strip()
            return t if t else None
        except (EOFError, KeyboardInterrupt):
            print(f"\n{warn('İptal edildi.')}")
            sys.exit(0)

    print(warn("  Geçersiz seçim, hemen gönderiliyor."))
    return None


def prompt_attachments() -> list[str] | None:
    """Terminalden interaktif olarak ek dosya yolları alır."""
    print()
    print(title("  📎 Ek dosyalar"))
    print(dim("  ─────────────────────────────"))
    print(dim("  Birden fazla dosya için virgülle ayırın. Örn: brosur.pdf, fiyat.xlsx"))
    print(dim("  Ek eklemek istemiyorsanız 'yok' veya boş bırakın."))
    print()

    try:
        raw = input(dim("  Dosya yolları (yok=ekleme): ")).strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{warn('İptal edildi.')}")
        sys.exit(0)

    if not raw or raw.lower() == "yok":
        return []

    paths = [p.strip() for p in raw.split(",") if p.strip()]
    return paths if paths else []


def resolve_attachments(paths: list[str]) -> list[Path]:
    """Ek dosya yollarını çözümler (proje köküne göre)."""
    resolved = []
    for p in paths:
        path = Path(p)
        if not path.is_absolute():
            path = ROOT_DIR / path
        resolved.append(path)
    return resolved


def cmd_send(
    send_at: str | None = None,
    interactive: bool = True,
    attach: list[str] | None = None,
    dry_run: bool = False,
    delay: int | None = None,
    retry_failed: bool = False,
) -> None:
    """Her alıcıya mail gönder."""
    paths = get_paths()
    smtp_config = get_smtp_config()

    # Alıcı kaynağı: --retry-failed ise failed.txt, değilse alicilar.txt
    recipient_path = paths["alicilar"].parent / "failed.txt" if retry_failed else paths["alicilar"]
    if retry_failed and not recipient_path.exists():
        print(error("  ✗ failed.txt bulunamadı. Önce başarısız gönderim olmalı."), file=sys.stderr)
        sys.exit(1)

    # Alıcıları yükle ve format kontrolü (banner'dan önce, hızlı hata)
    try:
        recipients = load_recipients(recipient_path)
    except ValidationError as e:
        print(error(f"  ✗ {e.message}"), file=sys.stderr)
        if e.details:
            print(dim(f"    {e.details}"), file=sys.stderr)
        sys.exit(1)

    if not recipients:
        src_name = "failed.txt" if retry_failed else "alicilar.txt"
        print(warn(f"  ⚠ {src_name} içinde geçerli alıcı yok."), file=sys.stderr)
        sys.exit(1)

    invalid = [r for r in recipients if not is_valid_email(r.email)]
    if invalid:
        print(error("  ✗ Geçersiz e-posta formatı bulundu:"), file=sys.stderr)
        for r in invalid:
            print(dim(f"    • {r.email} ({r.name}, {r.company})"), file=sys.stderr)
        print(dim("    Dosyayı düzeltip tekrar deneyin."), file=sys.stderr)
        sys.exit(1)

    print(banner())

    if dry_run:
        print(warn("  🔍 Önizleme modu — mail gönderilmeyecek."))
        print()

    if not dry_run:
        try:
            validate_smtp_config(smtp_config, require_credentials=True)
        except ConfigError as e:
            print(error(f"  ✗ {e.message}"), file=sys.stderr)
            if e.details:
                print(dim(f"    {e.details}"), file=sys.stderr)
            sys.exit(1)

    print(dim("  📮 Gönderim: SMTP"))

    if not paths["subject"].exists() or not paths["body_txt"].exists():
        print(error("  ✗ templates/subject.txt ve templates/body.txt bulunmalı."), file=sys.stderr)
        sys.exit(1)

    # Ek dosyalar: --attach > .env ATTACHMENTS > interaktif prompt (dry-run'da atla)
    attachment_paths: list[str] = []
    if attach:
        attachment_paths = [str(p) for p in resolve_attachments(attach)]
    elif get_attachments():
        attachment_paths = [str(p) for p in resolve_attachments(get_attachments())]
    elif interactive and sys.stdin.isatty() and not dry_run:
        chosen = prompt_attachments()
        if chosen:
            attachment_paths = [str(p) for p in resolve_attachments(chosen)]

    # Eksik dosya ve boyut kontrolü
    for ap in attachment_paths:
        if not Path(ap).exists():
            print(error(f"  ✗ Ek dosya bulunamadı: {ap}"), file=sys.stderr)
            sys.exit(1)
    if attachment_paths and not dry_run:
        try:
            check_attachment_sizes(attachment_paths)
        except SendError as e:
            print(error(f"  ✗ {e.message}"), file=sys.stderr)
            sys.exit(1)

    if attachment_paths:
        print(dim(f"  📎 Ekler: {', '.join(Path(p).name for p in attachment_paths)}"))

    # Dry-run: önizleme göster ve çık
    if dry_run:
        recipient = recipients[0]
        subject, body_text, body_html = build_message(recipient, paths)
        print(title("  📋 Önizleme (ilk alıcı için)"))
        print(separator())
        print(dim(f"  Alıcı: {recipient.email} ({recipient.name}, {recipient.company})"))
        print()
        print(dim("  Konu:"))
        print(f"  {subject}")
        print()
        print(dim("  İçerik (metin):"))
        for line in body_text.splitlines()[:15]:
            print(f"  │ {line}")
        if body_text.count("\n") >= 15:
            print(dim("  │ ..."))
        print(separator())
        print(dim(f"  Toplam {len(recipients)} alıcıya gönderilecek."))
        if len(recipients) <= 5:
            for r in recipients:
                print(dim(f"    • {r.email}"))
        else:
            for r in recipients[:3]:
                print(dim(f"    • {r.email}"))
            print(dim(f"    ... ve {len(recipients) - 3} alıcı daha"))
        print()
        return

    # Zamanlama: --at > .env SEND_AT > interaktif prompt
    target_time = None
    if send_at:
        target_time = parse_send_time(send_at)
        if not target_time:
            print(error(f"  ✗ Geçersiz tarih/saat formatı: {send_at}"), file=sys.stderr)
            print(dim("    Örnekler: 2025-02-28 14:30 | 28.02.2025 14:30 | 14:30"), file=sys.stderr)
            sys.exit(1)
    elif get_send_at():
        target_time = parse_send_time(get_send_at())
    elif interactive and sys.stdin.isatty() and not dry_run:
        chosen = prompt_send_time()
        if chosen:
            target_time = parse_send_time(chosen)
            if not target_time:
                print(warn("  Geçersiz format, hemen gönderiliyor."))
                target_time = None

    if target_time and target_time > datetime.now():
        send_delay_val = delay if delay is not None else get_send_delay()

        # Planı kaydet — launchd/at için
        scheduled_file = ROOT_DIR / "scheduled.json"
        schedule_data = {
            "send_at": target_time.strftime(SCHEDULED_DATETIME_FMT),
            "attach": attachment_paths,
            "delay": send_delay_val,
        }
        scheduled_file.write_text(json.dumps(schedule_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Sistem zamanlayıcısına kaydet
        if schedule_system(target_time):
            print()
            print(success(f"  ✓ Gönderim planlandı: {target_time.strftime('%d.%m.%Y %H:%M')}"))
            print(dim(f"    PC kapatılsa bile sistem zamanlayıcısına kaydedildi."))
            print(dim(f"    Uykudan uyanınca kaçırılan görev çalışır. Log: scheduled_send.log"))
            print()
            return

        # Sistem zamanlayıcısı yoksa arka plan süreci (terminal açık kalmalı)
        log_file = ROOT_DIR / "scheduled_send.log"
        with open(log_file, "w", encoding="utf-8") as f:
            subprocess.Popen(
                [sys.executable, "-m", "mailbot", "send-scheduled"],
                cwd=str(ROOT_DIR),
                stdout=f,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        print()
        print(success(f"  ✓ Gönderim planlandı: {target_time.strftime('%d.%m.%Y %H:%M')}"))
        print(warn(f"    Sistem zamanlayıcısı kullanılamadı — terminal açık kalmalı."))
        print(dim(f"    Log: scheduled_send.log"))
        print()
        return

    # Gecikme: --delay > .env SEND_DELAY (her mail arası saniye)
    send_delay = delay if delay is not None else get_send_delay()
    if send_delay > 0:
        print(dim(f"  ⏱ Her mail arası {send_delay} sn bekleme"))

    print()
    print(title(f"  📤 {len(recipients)} alıcıya mail gönderiliyor..."))
    print(separator())

    failed: list[tuple[Recipient, str]] = []
    failed_path = ROOT_DIR / "failed.txt"

    # Gönderim: SMTP
    smtp_dict = smtp_config.to_dict() if hasattr(smtp_config, "to_dict") else smtp_config
    for i, recipient in enumerate(recipients, 1):
        try:
            subject, body_text, body_html = build_message(recipient, paths)
            message = EmailMessage(
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                from_addr=smtp_dict["from_addr"],
                to_addr=recipient.email,
                attachments=attachment_paths if attachment_paths else None,
                reply_to=smtp_dict.get("reply_to"),
                cc=smtp_dict.get("cc"),
                bcc=smtp_dict.get("bcc"),
            )
            send_email(message, recipient, smtp_dict)
            bar = progress_bar(i, len(recipients))
            print(f"  {success('✓')} {bar} {recipient.email}")
        except Exception as e:
            err_msg = getattr(e, "message", str(e))
            bar = progress_bar(i, len(recipients))
            print(f"  {error('✗')} {bar} {recipient.email}: {err_msg}", file=sys.stderr)
            failed.append((recipient, err_msg))
        # Her mail arası gecikme (zamanlanmış gönderimde de saat geldikten sonra uygulanır)
        if send_delay > 0 and i < len(recipients):
            time.sleep(send_delay)

    print(separator())

    # Başarısızları failed.txt'ye kaydet
    if failed:
        lines = [f"{r.email}/{r.name}/{r.company}" for r, _ in failed]
        failed_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(warn(f"  ⚠ {len(failed)} alıcıya ulaşılamadı → failed.txt"))
        print(dim(f"    Tekrar denemek için: failed.txt içeriğini alicilar.txt'e ekleyin."))

    print(success(f"  ✓ Tamamlandı. ({len(recipients) - len(failed)} başarılı, {len(failed)} başarısız)"))
    print()


def cmd_send_scheduled() -> None:
    """Planlanmış gönderimi çalıştırır (arka plan süreci)."""
    scheduled_file = ROOT_DIR / "scheduled.json"
    if not scheduled_file.exists():
        print(error("  ✗ scheduled.json bulunamadı."), file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(scheduled_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(error(f"  ✗ scheduled.json geçersiz JSON: {e}"), file=sys.stderr)
        sys.exit(1)

    send_at_str = data.get("send_at")
    if not send_at_str:
        print(error("  ✗ scheduled.json içinde send_at eksik."), file=sys.stderr)
        sys.exit(1)

    attach = data.get("attach", [])
    delay_val = data.get("delay", 0)

    try:
        target = datetime.strptime(send_at_str, SCHEDULED_DATETIME_FMT)
    except ValueError:
        print(error(f"  ✗ Geçersiz tarih formatı: {send_at_str}"), file=sys.stderr)
        sys.exit(1)
    now = datetime.now()
    if target > now:
        sleep_secs = (target - now).total_seconds()
        time.sleep(sleep_secs)

    # Planlanan saat geldi — hemen gönder
    scheduled_file.unlink(missing_ok=True)
    cmd_send(
        send_at=None,
        interactive=False,
        attach=attach if attach else None,
        dry_run=False,
        delay=delay_val,
    )


def cmd_init() -> None:
    """Proje yapısını oluştur (zaten varsa atla)."""
    print(banner())
    root = Path(__file__).resolve().parent.parent

    (root / "alicilar.txt").touch(exist_ok=True)
    (root / "templates").mkdir(exist_ok=True)
    (root / "templates" / "subject.txt").write_text(
        "Merhaba {{ name }} - {{ company }} için özel teklif\n", encoding="utf-8"
    )
    (root / "templates" / "body.txt").write_text(
        "Merhaba {{ name }},\n\n{{ company }} ile ilgili size özel bir teklifimiz var.\n\nİletişim: {{ email }}\n",
        encoding="utf-8",
    )
    (root / "templates" / "signature.txt").write_text(
        "Saygılarımızla,\nMail Bot\n",
        encoding="utf-8",
    )
    (root / "templates" / "signature.html").write_text(
        '<div class="signature" style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #eee; color: #666; font-size: 14px;">\n'
        "    Saygılarımızla,<br>\n"
        "    <strong>Mail Bot</strong>\n"
        "</div>\n",
        encoding="utf-8",
    )

    env_example = root / ".env.example"
    env_file = root / ".env"
    if env_example.exists() and not env_file.exists():
        env_file.write_text(env_example.read_text(encoding="utf-8"), encoding="utf-8")
        print(title("  📁 .env oluşturuldu (.env.example'dan). SMTP bilgilerini düzenleyin."))
    elif not env_file.exists():
        env_file.write_text(
            "SMTP_HOST=smtp.gmail.com\nSMTP_PORT=587\nSMTP_USER=\nSMTP_PASS=\nSMTP_FROM=\nSMTP_USE_TLS=true\n",
            encoding="utf-8",
        )
        print(title("  📁 .env oluşturuldu. SMTP bilgilerini doldurun."))

    print()
    print(success("  ✓ Proje yapısı hazır."))
    print()


def main() -> None:
    """CLI giriş noktası. MailBotError türevlerini yakalar."""
    try:
        _main()
    except (ValidationError, ConfigError) as e:
        print(error(f"  ✗ {e.message}"), file=sys.stderr)
        if e.details:
            print(dim(f"    {e.details}"), file=sys.stderr)
        sys.exit(1)


def _main() -> None:
    parser = argparse.ArgumentParser(description="Mail Bot - Şablon tabanlı toplu mail gönderimi")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    send_parser = subparsers.add_parser("send", help="Mailleri gönder")
    send_parser.add_argument(
        "--at",
        metavar="TARIH_SAAT",
        help="Gönderim zamanı (örn: 2025-02-28 14:30, 28.02.2025 14:30, 14:30)",
    )
    send_parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Soru sormadan hemen gönder (interaktif menüyü atla)",
    )
    send_parser.add_argument(
        "-a", "--attach",
        metavar="DOSYA",
        action="append",
        dest="attach",
        help="Eklenecek dosya (birden fazla -a ile eklenebilir)",
    )
    send_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Göndermeden önce konu ve içeriği önizle",
    )
    send_parser.add_argument(
        "--delay",
        type=int,
        metavar="SANİYE",
        help="Her mail arası bekleme (Gmail sınırları için örn: 2-3)",
    )
    send_parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="failed.txt içindeki alıcılara tekrar gönder",
    )

    subparsers.add_parser("init", help="Proje yapısını oluştur")
    subparsers.add_parser("send-scheduled", help="(Dahili) Planlanmış gönderimi çalıştırır")

    args = parser.parse_args()

    if args.cmd == "send":
        try:
            cmd_send(
            send_at=args.at,
            interactive=not args.yes,
            attach=args.attach or None,
            dry_run=args.dry_run,
            delay=args.delay,
            retry_failed=getattr(args, "retry_failed", False),
            )
        except (ValidationError, ConfigError):
            raise
        except MailBotError as e:
            print(error(f"  ✗ {e.message}"), file=sys.stderr)
            sys.exit(1)
    elif args.cmd == "init":
        cmd_init()
    elif args.cmd == "send-scheduled":
        cmd_send_scheduled()
    else:
        print(f"Bilinmeyen komut: {args.cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
