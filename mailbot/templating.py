"""Jinja2 ile şablon render."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from .config import (
    get_sender_name,
    get_sender_phone,
    get_sender_email,
    get_sender_linkedin,
    get_sender_linkedin_label,
    get_sender_website,
    get_sender_social_media_label,
    get_sender_address,
    get_sender_title,
    get_sender_logo_url,
    get_vizyon_canva_link,
)
from .models import Recipient
from .exceptions import TemplateError


def build_message(recipient: Recipient, paths: dict) -> tuple[str, str, str | None]:
    """
    Alıcı için subject, body_text ve body_html üretir.
    İmza dosyaları varsa body sonuna eklenir.
    Returns: (subject, body_text, body_html | None)
    """
    try:
        templates_dir = paths["templates"]
        env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

        context = {
            **recipient.to_context(),
            "sender_name": get_sender_name(),
            "sender_phone": get_sender_phone(),
            "sender_email": get_sender_email(),
            "sender_linkedin": get_sender_linkedin(),
            "sender_linkedin_label": get_sender_linkedin_label(),
            "sender_website": get_sender_website(),
            "sender_social_media_label": get_sender_social_media_label(),
            "sender_address": get_sender_address(),
            "sender_title": get_sender_title(),
            "sender_logo_url": get_sender_logo_url(),
            "vizyon_canva_link": get_vizyon_canva_link(),
        }

        subject = env.get_template("subject.txt").render(**context)
        body_text = env.get_template("body.txt").render(**context)

        # İmza (metin)
        if paths["signature_txt"].exists():
            sig_text = env.get_template("signature.txt").render(**context)
            body_text = body_text.rstrip() + "\n\n" + sig_text

        body_html = None
        if paths["body_html"].exists():
            body_html = env.get_template("body.html").render(**context)

            # İmza (HTML)
            if paths["signature_html"].exists():
                sig_html = env.get_template("signature.html").render(**context)
            elif paths["signature_txt"].exists():
                sig_text = env.get_template("signature.txt").render(**context)
                sig_html = f'<div class="signature" style="margin-top:20px;color:#666;">{sig_text.replace(chr(10), "<br>")}</div>'
            else:
                sig_html = None

            if sig_html:
                pos = body_html.rfind("</body>")
                if pos != -1:
                    body_html = body_html[:pos] + sig_html + "\n" + body_html[pos:]
                else:
                    body_html = body_html + sig_html

        return subject, body_text, body_html
    except TemplateNotFound as e:
        raise TemplateError(f"Şablon bulunamadı: {e.name}", details=str(e))
    except TemplateError:
        raise
    except Exception as e:
        raise TemplateError(f"Şablon hatası: {e}", details=str(e))
