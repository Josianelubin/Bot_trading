"""Telegram en ENVOI SEUL : le bot n'ecoute aucune commande et ne peut declencher aucun trade."""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _api(method):
    return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"


def _configured():
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


def _ok(r):
    try:
        return r.status_code == 200 and r.json().get("ok") is True
    except ValueError:
        return False


def send_message(text, session=None):
    """Envoie un message texte. Retourne True seulement si Telegram confirme."""
    if not _configured():
        return False
    try:
        ok = _ok((session or requests).post(
            _api("sendMessage"), json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text[:4000],
                                       "disable_web_page_preview": True}, timeout=10))
    except requests.RequestException:
        ok = False
    if not ok:
        logger.error("Echec envoi Telegram (message)")  # jamais le token dans les logs
    return ok


def send_photo(image_bytes, caption="", session=None):
    if not _configured():
        return False
    try:
        r = (session or requests).post(
            _api("sendPhoto"), data={"chat_id": settings.TELEGRAM_CHAT_ID, "caption": caption[:1000]},
            files={"photo": ("analyse.png", image_bytes)}, timeout=20)
        ok = _ok(r)
    except requests.RequestException:
        ok = False
    if not ok:
        logger.error("Echec envoi Telegram (photo)")
    return ok
