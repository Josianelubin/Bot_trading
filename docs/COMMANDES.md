# KPS - commandes

## Installation (Termux)
pkg install python unzip
unzip kps-projet.zip && cd kps
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env

## Base de donnees + compte
python manage.py migrate
export $(grep -v '^#' .env | xargs)
python manage.py create_owner

## Verifier
python manage.py check
python manage.py test tests
python manage.py send_test

## Lancer
python manage.py run_bot --once --dry-run    # test sans Telegram ni base
python manage.py run_bot --once              # 1 cycle reel (propositions sur Telegram)
python manage.py run_bot                     # boucle continue
python manage.py runserver                   # dashboard (autre session Termux)

## Execution des trades (Phase 10-11)
1. Variables DEMO : GATEIO_TESTNET_API_KEY / GATEIO_TESTNET_API_SECRET / GATEIO_TESTNET_BASE_URL (a verifier dans la doc Gate)
2. python manage.py migrate        # applique 0002_execution
3. python manage.py runserver  +  python manage.py run_bot
4. Telegram : ACCEPTER -> ouvrir le lien -> definir entree / SL / TP -> EXECUTE TRADE
5. Dashboard /trades/positions/ : positions, gagnant/perdant, PNL (bouton Synchroniser)
