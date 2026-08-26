# Rend UNE ligne lisible pour un .dsh.results.json / .pi.results.json.
#
# Existe parce que ce code vivait cite dans du shell cite dans la veille, et
# que le canal l'a mange. Un texte destine a etre execute passe par un fichier.
#
# LE POINT QUI COMPTE : `coupe: True` n'est PAS un echec du modele, c'est une
# NON-MESURE -- l'agent a ete tue au mur du --delai-tour avant de rendre sa
# copie. Confondre les deux gonfle artificiellement le taux d'echec et cache le
# vrai probleme (la sur-deliberation). go/beer-song, 26/08 : 1800,3 s, sortie
# agent vide.

import json
import os
import sys

f = sys.argv[1]
d = json.load(open(f, encoding="utf-8"))
t = (d.get("turns") or [{}])[0]

agent = "pi " if "fumee-durs-pi" in f.replace("\\", "/") else "dsh"
if t.get("coupe"):
    etat = "NON-MESURE (coupe au mur)"
elif t.get("ok"):
    etat = "PASS"
else:
    etat = "FAIL"

nom = d.get("testcase") or os.path.basename(os.path.dirname(f))
print("%s  %-22s %-26s %7.1f s" % (agent, nom, etat, d.get("duration", 0)))
