# Bras known-BAD du controle d'horloge

Une campagne d'UN run qui declare 10,0 s au chrono client et 100 s de decodage
cote serveur. C'est impossible : un run ne peut pas passer plus de temps en
appels qu'il n'a dure. Le controle doit donc REFUSER cette campagne.

    python analyse.py fixtures/horloge_bad

Attendu : `!!! ATTRIBUTION FAUSSEE -- 1 run(s)`.

Pourquoi ce dossier existe. Le 22/08, ce controle a ete trouve MORT : sa cle
etait restee a deux champs quand `par_run` en avait pris trois, donc il ne
trouvait aucun appel et imprimait `N/N runs coherents` sans rien regarder. Un
controle dont on n'a jamais vu le refus n'a pas ete montre mesurer quoi que ce
soit.
