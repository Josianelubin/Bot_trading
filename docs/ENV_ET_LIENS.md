# Variables d'environnement, liens, passage DEMO -> REEL, IP

## NewsAPI
Cle gratuite : https://newsapi.org/register   (variable NEWSAPI_KEY)
Plan Developer : 100 requetes/jour, articles retardes de 24 h, usage developpement/test seulement
(voir https://newsapi.org/pricing). Le bot limite ses appels (KPS_NEWSAPI_DAILY_LIMIT, cache 6 h).

## Passer du DEMO au REEL
1. Tests testnet reussis (ordre ouvert, SL/TP presents, marge isolee, resultat correct).
2. Cle Gate.io REELLE : droits Futures lecture+ecriture, JAMAIS retrait, liste blanche IP si possible.
3. Variables : GATEIO_API_KEY, GATEIO_API_SECRET, KPS_ALLOW_LIVE=true, KPS_TRADING_MODE=REAL
4. Redemarrer. Le badge devient rouge REAL ; chaque execution demande de taper REAL.
5. Commencer avec KPS_DEFAULT_CAPITAL_USDT et KPS_DEFAULT_LEVERAGE tres bas.
Retour : KPS_TRADING_MODE=DEMO. Les donnees DEMO et REEL restent separees.

## IP du site sur Render
Tableau de bord Render -> ton service -> bouton Connect (en haut a droite) -> onglet Outbound.
Les IP sont des plages CIDR partagees dans la region. IP dediees : plan Pro + frais mensuels.
python manage.py show_ip affiche l'IP sortante du moment (Shell Render).
