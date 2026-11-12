import json
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


def send_message(text, reply_markup=None, session=None):
    """Envoie un message texte. Retourne True seulement si Telegram confirme."""
    if not _configured():
        return False
    payload = {"chat_id": settings.TELEGRAM_CHAT_ID, "text": text[:4000]}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        ok = _ok((session or requests).post(_api("sendMessage"), json=payload, timeout=10))
    except requests.RequestException:
        ok = False
    if not ok:
        logger.error("Echec envoi Telegram (message)")  # jamais le token dans les logs
    return ok


def send_photo(image_bytes, caption="", session=None):
    """Envoie une image (PNG/JPEG en bytes) avec legende."""
    if not _configured():
        return False
    try:
        r = (session or requests).post(
            _api("sendPhoto"),
            data={"chat_id": settings.TELEGRAM_CHAT_ID, "caption": caption[:1000]},
            files={"photo": ("analyse.png", image_bytes)},
            timeout=20,
        )
        ok = _ok(r)
    except requests.RequestException:
        ok = False
    if not ok:
        logger.error("Echec envoi Telegram (photo)")
    return ok


def approval_keyboard(proposal_id):
    """Boutons Accepter / Modifier / Rejeter (traites en Phase 10)."""
    return json.dumps({"inline_keyboard": [[
        {"text": "ACCEPTER", "callback_data": f"accept:{proposal_id}"},
        {"text": "MODIFIER", "callback_data": f"edit:{proposal_id}"},
        {"text": "REJETER", "callback_data": f"reject:{proposal_id}"},
    ]]})


def get_updates(offset=None, timeout=0, session=None):
    """Recupere les clics sur les boutons. Retourne une liste (vide si erreur)."""
    if not _configured():
        return []
    params = {"timeout": timeout, "allowed_updates": json.dumps(["callback_query"])}
    if offset is not None:
        params["offset"] = offset
    try:
        r = (session or requests).get(_api("getUpdates"), params=params, timeout=timeout + 10)
        if r.status_code == 200 and r.json().get("ok"):
            return r.json().get("result", [])
    except (requests.RequestException, ValueError):
        pass
    logger.error("Echec lecture Telegram (getUpdates)")
    return []


def answer_callback(callback_id, text, session=None):
    if not _configured():
        return False
    try:
        return _ok((session or requests).post(_api("answerCallbackQuery"),
                                              json={"callback_query_id": callback_id, "text": text[:190]}, timeout=10))
    except requests.RequestException:
        return False
