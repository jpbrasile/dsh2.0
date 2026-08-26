# QUELS FOURNISSEURS CACHENT CE MODELE ? -- la question qui decide de la suite.
#
# CE QUI A ETE MESURE LE 26/08. Sur un exercice dur joue par dsh, 14 appels de
# l'agent, TOUS servis par AkashML, cache declare 0 sur 388 760 jetons
# d'entree : chaque appel re-prefille la conversation entiere. Le prefixe
# envoye par dsh est pourtant reutilisable a 80,8 % (ou_casse_le_prefixe.py) --
# le harnais n'est pas en cause, le routage l'est. Un autre run le meme jour a
# obtenu 41,4 % de cache : le taux depend du fournisseur qu'OpenRouter choisit,
# pas de nous.
#
# CE QUE CE SCRIPT FAIT. Il demande a OpenRouter la liste des points de service
# du modele et ce que chacun sait faire. Aucun appel d'inference : c'est un GET
# de catalogue, gratuit.
#
# CE QU'IL NE FAIT PAS. Il ne choisit rien et n'ecrit dans aucune config. Le
# catalogue annonce une capacite ; seule une mesure au fil dira si le cache est
# reellement servi. C'est la meme discipline que pour le champ `fournisseur` :
# epingler dans la requete ne prouve rien, seule la reponse prouve.
#
#     python fournisseurs_qui_cachent.py [modele]

import io
import json
import os
import sys
import urllib.request

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELE = sys.argv[1] if len(sys.argv) > 1 else "qwen/qwen3.8-27b"


def charger_env(chemin):
    if not os.path.exists(chemin):
        return
    for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        k, v = ligne.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


charger_env(os.path.join(RACINE, ".env"))
cle = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_KEY")

req = urllib.request.Request(
    "https://openrouter.ai/api/v1/models/%s/endpoints" % MODELE,
    headers={"Authorization": "Bearer %s" % cle} if cle else {})
with urllib.request.urlopen(req, timeout=60) as r:
    d = json.loads(r.read().decode("utf-8", "replace"))

pts = ((d.get("data") or {}).get("endpoints")) or []
print("modele : %s   %d points de service" % (MODELE, len(pts)))
print()
print("  %-18s %-9s %-11s %-11s %-9s %s"
      % ("fournisseur", "contexte", "$/M entree", "$/M cache", "quantif", "cache ?"))
for p in sorted(pts, key=lambda x: (x.get("provider_name") or "")):
    pr = p.get("pricing") or {}
    lecture = pr.get("input_cache_read")
    ecriture = pr.get("input_cache_write")
    # Un tarif de LECTURE de cache est le seul temoin declaratif fiable : un
    # fournisseur qui ne facture pas la lecture de cache n'en fait pas.
    cache = "OUI" if (lecture not in (None, "", "0")) else "non"
    def m(x):
        try:
            return "%.3f" % (float(x) * 1e6)
        except (TypeError, ValueError):
            return "-"
    print("  %-18s %-9s %-11s %-11s %-9s %s"
          % ((p.get("provider_name") or "?")[:18],
             p.get("context_length"), m(pr.get("prompt")), m(lecture),
             (p.get("quantization") or "-"), cache))
print()
print("  $/M cache = tarif de LECTURE d'un jeton deja cache. Absent = le")
print("  fournisseur ne facture pas la lecture de cache, donc n'en sert pas.")
print("  Pour epingler dans une requete OpenAI-compatible :")
print('    "provider": {"order": ["<nom>"], "allow_fallbacks": false}')
