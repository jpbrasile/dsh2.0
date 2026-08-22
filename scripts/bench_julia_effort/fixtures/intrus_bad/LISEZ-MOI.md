# Bras known-BAD du controle de partage du serveur

Deux runs sains, et UNE conversation etrangere (messages 41 -> 45) dont les
appels tombent a cheval sur les deux fenetres. Aucun run ne depasse sa duree :
ni le controle d'horloge ni celui d'echeance ne peuvent la voir.

    python analyse.py fixtures/intrus_bad

Attendu : `!!! SERVEUR PARTAGE -- 1 conversation(s) traversent plusieurs runs.`

Pourquoi ce dossier existe : le 22/08 un agent etranger a partage le serveur
avec la campagne pendant 39 minutes, ~2010 s de decodage, sans qu'aucun nombre
publie ne le montre.
