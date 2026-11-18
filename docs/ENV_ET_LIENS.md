# Variables d'environnement et liens (voir aussi .env.example)

## Base de donnees (SQLite OU PostgreSQL, meme code)
Local (Termux)  : DATABASE_URL=sqlite:///db.sqlite3
Render / Postgres : DATABASE_URL=postgres://utilisateur:motdepasse@hote:5432/nombase   (+ KPS_DB_SSL=true si connexion externe)

## Render : si "relation auth_user does not exist"
Shell du service -> python manage.py migrate && python manage.py create_owner
(le Dockerfile fait maintenant migrate + collectstatic + create_owner a chaque demarrage)

## Liste blanche IP Gate.io
python manage.py show_ip     (IP publique sortante de la machine qui execute le bot)
Gate.io : https://www.gate.com/myaccount/profile/api-key/manage -> Creer une cle API v4 -> champ "IP" (liste blanche)

## Liens
Telegram BotFather : https://t.me/BotFather
Gate.io doc API    : https://www.gate.com/docs/developers/apiv4/
GDELT (sans cle)   : https://www.gdeltproject.org
CryptoPanic        : https://cryptopanic.com/developers/api/
Render             : https://render.com
Lucide (icones)    : https://lucide.dev/icons
