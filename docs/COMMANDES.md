# KPS - commandes

## Installation (Termux)
cp -r /storage/emulated/0/Download/kps ~/kps && cd ~/kps
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env

## Preparation (une fois)
python manage.py migrate
python manage.py create_owner
python manage.py check
python manage.py test tests
python manage.py send_test

## Lancer (2 sessions Termux, venv active)
python manage.py runserver        # le site : http://127.0.0.1:8000
termux-wake-lock && python manage.py run_bot   # analyses -> site + Telegram (envoi seul)

## Test sans rien envoyer
python manage.py run_bot --once --dry-run
python manage.py run_bot --once --symbols BTC_USDT,XAUT_USDT

## Prendre un trade : UNIQUEMENT sur le site
Analyses -> (symbole) -> Preparer un trade, ou Propositions -> trade
-> definir entree / SL / TP -> case de confirmation -> EXECUTE TRADE
Positions : /trades/positions/

## Page Live (graphique en direct, bouton SCANNER)
http://127.0.0.1:8000/live/   (apres connexion, la page d'accueil y redirige)
- Timeframes : 1m 5m 15m 30m 1h 4h 8h 1D 1W
- SCANNER : analyse les bougies CLOTUREES du graphique -> entree / SL / TP1-3 ou ATTENTE
- Direct : WebSocket Gate Futures USDT (repli : actualisation toutes les 10 s)
- ARRET D'URGENCE : bloque toute NOUVELLE position
