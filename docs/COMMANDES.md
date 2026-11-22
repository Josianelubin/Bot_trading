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

## Strategie ICT du scanner (page /live/)
Setup : CHoCH/MSS -> deplacement (imbalance) -> retracement en zone OTE (62-79 %) avec FVG / Order Block / sweep de liquidite
Entree : milieu de la confluence FVG/OB dans l'OTE (sinon 70,5 %) ; Stop : sous l'origine de la jambe ; TP1 = sommet (liquidite), TP2/TP3 = extensions -27 % / -62 %
Gain/perte potentiels : % du prix, % de la marge (x levier) et USDT, selon capital et levier saisis.
Reussite/echec : bouton "Reussite historique (backtest)" = calcul sur l'historique reel, jamais invente.

## Logos des cryptos (vrais logos)
Chaque paire affiche le vrai logo de sa crypto : CoinGecko (image officielle), puis 2 sources de secours ; stocke en base.
python manage.py fetch_logos      # telecharge d'un coup tous les logos des paires Gate (facultatif : sinon a la demande)
Variable facultative : COINGECKO_API_KEY (cle "demo" gratuite : https://www.coingecko.com/en/api)

## Analyse AUTOMATIQUE par le site (plus besoin de run_bot)
Lance seulement : python manage.py runserver   (ou gunicorn sur Render)
A la premiere visite du site, un moteur d'arriere-plan analyse toutes les paires toutes les KPS_SCAN_INTERVAL_SECONDS
et envoie les resultats sur Telegram. Sur la page /live/ : bloc "Bot d'analyse automatique" (Demarrer / Arreter / Analyser maintenant).
KPS_AUTORUN=false desactive ce moteur (alors : python manage.py run_bot). Un seul moteur tourne a la fois (verrou en base).
Render gratuit : le service s'endort sans visite -> l'analyse s'arrete ; un worker (payant) ou un ping regulier la garde active.
