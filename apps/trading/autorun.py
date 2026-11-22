"""Analyse AUTOMATIQUE lancee par le site (aucune commande `run_bot` necessaire).
Un fil d'arriere-plan demarre a la premiere requete du site. Un verrou en base (lease + heartbeat) garantit qu'UN SEUL
moteur tourne, meme avec plusieurs processus (gunicorn) ou en meme temps que la commande run_bot."""
import logging
import os
import socket
import threading
import time
import traceback
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections
from django.db.models import Q
from django.utils import timezone

from .models import BotStatus

log = logging.getLogger(__name__)
LEASE_SECONDS = 90
OWNER = f"web:{socket.gethostname()}:{os.getpid()}"
_started, _lock = False, threading.Lock()


def cli_owner():
    return f"cli:{socket.gethostname()}:{os.getpid()}"


def get_status():
    obj, _ = BotStatus.objects.get_or_create(pk=1)
    return obj


def acquire(owner=OWNER, now=None):
    """Prend ou renouvelle le verrou. True si ce processus est le moteur actif."""
    now = now or timezone.now()
    get_status()
    n = BotStatus.objects.filter(pk=1).filter(
        Q(owner="") | Q(owner=owner) | Q(heartbeat__isnull=True) | Q(heartbeat__lt=now - timedelta(seconds=LEASE_SECONDS))
    ).update(owner=owner, heartbeat=now)
    return n == 1


def status_dict():
    st = get_status()
    now = timezone.now()
    alive = bool(st.heartbeat and (now - st.heartbeat).total_seconds() < LEASE_SECONDS and st.owner)
    nxt = None
    if st.enabled and st.last_cycle_at:
        nxt = st.last_cycle_at + timedelta(seconds=settings.KPS_SCAN_INTERVAL_SECONDS)
    return {"autorun": settings.KPS_AUTORUN, "enabled": st.enabled, "running": st.running and alive, "engine_alive": alive,
            "owner": st.owner if alive else "", "cycles": st.cycles, "interval_seconds": settings.KPS_SCAN_INTERVAL_SECONDS,
            "last_cycle_at": st.last_cycle_at.isoformat() if st.last_cycle_at else None,
            "next_cycle_at": nxt.isoformat() if nxt else None, "run_requested": st.run_requested,
            "last_summary": st.last_summary, "last_error": st.last_error}


def _cycle(runner):
    lines, errs = [], []
    runner.log = lambda m: lines.append(str(m))
    runner.err = lambda m: errs.append(str(m))
    runner.heartbeat = lambda: acquire()
    BotStatus.objects.filter(pk=1).update(running=True, run_requested=False, last_started_at=timezone.now())
    summary = {}
    try:
        summary = runner.cycle() or {}
    except Exception as e:  # le moteur ne doit jamais s'arreter
        errs.append(f"{type(e).__name__}: {e}")
        log.error("Cycle en erreur : %s", traceback.format_exc())
    BotStatus.objects.filter(pk=1).update(
        running=False, last_cycle_at=timezone.now(), cycles=get_status().cycles + 1,
        last_summary=(f"{summary.get('symbols', 0)} symbole(s), {summary.get('proposals', 0)} proposition(s), "
                      f"{summary.get('news', 0)} actualite(s) nouvelle(s)\n" + "\n".join(lines[-25:]))[-4000:],
        last_error="\n".join(errs[-10:])[-2000:] if errs else "")


def _loop():
    from .runner import BotRunner
    runner = None
    while True:
        try:
            close_old_connections()
            if not acquire():
                time.sleep(15)
                continue
            st = get_status()
            now = timezone.now()
            due = st.enabled and (st.run_requested or st.last_cycle_at is None
                                  or (now - st.last_cycle_at).total_seconds() >= settings.KPS_SCAN_INTERVAL_SECONDS)
            if due:
                runner = runner or BotRunner()
                _cycle(runner)
            time.sleep(5)
        except Exception:
            log.error("Boucle autorun : %s", traceback.format_exc())
            time.sleep(30)  # base pas prete (migrations) ou erreur passagere : on reessaie
        finally:
            close_old_connections()


def ensure_started():
    """Demarre (une fois par processus) le fil d'analyse automatique. Sans effet si KPS_AUTORUN=false."""
    global _started
    if _started or not settings.KPS_AUTORUN:
        return _started
    with _lock:
        if not _started:
            threading.Thread(target=_loop, name="kps-autorun", daemon=True).start()
            _started = True
    return _started
