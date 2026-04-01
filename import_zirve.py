"""
import_zirve.py — Form verisi (TSV) → zirve_katilimcilari.txt

Kullanım:
    python import_zirve.py <tsv_dosyasi>
    python import_zirve.py kayitlar.tsv

TSV formatı (Google Form dışa aktarması):
    Zaman damgası\tAd Soyad\tEmail\tÖğrenci No\tTelefon\tYapay Zeka mı?\tBölüm\tSınıf\tKVKK
"""

import sys
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = ROOT_DIR / "zirve_katilimcilari.txt"

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip()))


def parse_tsv(content: str) -> list[dict]:
    """TSV içeriğini parse eder, geçerli kayıtları döndürür."""
    records = []
    lines = content.strip().splitlines()

    # İlk satır başlık satırı mı? Kontrol et
    start_idx = 0
    if lines and ("ad soyad" in lines[0].lower() or "name" in lines[0].lower() or "zaman" in lines[0].lower()):
        start_idx = 1  # başlık satırını atla

    for i, line in enumerate(lines[start_idx:], start=start_idx + 1):
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            continue

        # Sütun tespiti - esnek: email '@' içeren sütunu bul
        name = ""
        email = ""
        department = ""

        # Standart Google Form formatı: [timestamp, name, email, no, phone, ai_yn, dept, grade, kvkk]
        if len(parts) >= 9:
            name = parts[1].strip()
            email = parts[2].strip()
            department = parts[6].strip() if parts[6].strip() not in (".", "-", "", ",") else ""
        elif len(parts) >= 3:
            # En az 3 sütun: her birinde email ara
            for j, p in enumerate(parts):
                if "@" in p and is_valid_email(p.strip()):
                    email = p.strip()
                    name = parts[j - 1].strip() if j > 0 else ""
                    department = parts[j + 1].strip() if j + 1 < len(parts) else ""
                    break

        if not email:
            continue

        # email normalize (boşluk temizle, küçük harf)
        email = "".join(email.split()).lower()

        if not is_valid_email(email):
            print(f"  ⚠ Satır {i}: Geçersiz email atlandı → {email!r}")
            continue

        name = name.strip() or "Katılımcı"
        department = department.strip() or "BAU"

        records.append({"email": email, "name": name, "department": department})

    return records


def deduplicate(records: list[dict]) -> list[dict]:
    """Email'e göre tekrarları kaldır (ilk geçiş öncelikli)."""
    seen = set()
    unique = []
    dupes = 0
    for r in records:
        key = r["email"].lower()
        if key in seen:
            dupes += 1
            continue
        seen.add(key)
        unique.append(r)
    return unique, dupes


def load_existing_emails(output_file: Path) -> set[str]:
    """Mevcut dosyadaki email'leri oku (tekrar eklememek için)."""
    if not output_file.exists():
        return set()
    existing = set()
    for line in output_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("/", 1)
        if parts:
            existing.add(parts[0].strip().lower())
    return existing


def main() -> None:
    if len(sys.argv) < 2:
        print("Kullanım: python import_zirve.py <tsv_dosyasi>")
        print()
        print("Adımlar:")
        print("  1. Google Form → Excel/Sheet → Dosya olarak indir → TSV veya TXT olarak kaydet")
        print("  2. python import_zirve.py kayitlar.tsv")
        print()
        print(f"Çıktı: {OUTPUT_FILE}")
        sys.exit(1)

    tsv_path = Path(sys.argv[1])
    if not tsv_path.exists():
        print(f"Hata: Dosya bulunamadı → {tsv_path}")
        sys.exit(1)

    content = tsv_path.read_text(encoding="utf-8-sig")  # utf-8-sig: BOM varsa temizler

    print(f"📂 Okunuyor: {tsv_path}")
    records = parse_tsv(content)
    print(f"   {len(records)} geçerli kayıt bulundu.")

    records, dupes = deduplicate(records)
    if dupes:
        print(f"   {dupes} tekrar kayıt kaldırıldı.")

    existing = load_existing_emails(OUTPUT_FILE)
    new_records = [r for r in records if r["email"].lower() not in existing]
    skipped = len(records) - len(new_records)

    if skipped:
        print(f"   {skipped} kayıt zaten listede mevcut, atlandı.")

    if not new_records:
        print("✅ Eklenecek yeni kayıt yok. Liste güncel.")
        return

    # Dosyaya ekle
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n# {tsv_path.name} dosyasından içe aktarıldı\n")
        for r in new_records:
            f.write(f"{r['email']}/{r['name']}/{r['department']}\n")

    print(f"✅ {len(new_records)} yeni katılımcı → {OUTPUT_FILE}")
    print()
    print("Şimdi mail gönderebilirsin:")
    print("  python -m mailbot send --kampanya zirve --dry-run   # önizleme")
    print("  python -m mailbot send --kampanya zirve             # gönder")


if __name__ == "__main__":
    main()
