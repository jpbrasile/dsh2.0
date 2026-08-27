"""L'ECHELLE DE BUDGET : commencer bas et monter si le budget a mordu.

Le taux d'escalade a un barreau N, c'est P(pensee > N). On le lit sur les
appels qui ont pense LIBREMENT -- c'est la seule population qui montre la
longueur que le modele AURAIT prise.

Les tronques comptent comme « pensee > 32 768 » : on ne sait pas combien il
leur aurait fallu, mais on sait qu'ils depassent tous les barreaux.

Cout d'un barreau : un appel qui pense p jetons coute a peu pres
p / debit + prefill. Debit mesure sur ce bras : voir plus bas, on le
calibre sur les appels libres eux-memes plutot que de le supposer.
"""
import json, os, statistics as st

BASE = os.path.join(os.environ["USERPROFILE"], "Documents", "dsh2.0", "scripts", "gpqa")
recs = [json.loads(l) for l in
        open(os.path.join(BASE, "local_q4_t1_libre_tournant.jsonl"), encoding="utf-8") if l.strip()]

tr = [r for r in recs if r.get("finish_reason") == "length"]
li = [r for r in recs if r.get("finish_reason") != "length"]

# calibration caracteres -> jetons, prise sur les tronques (longueur exacte connue)
ratio = st.median([r["reponse_car"] / r["tokens_sortie"] for r in tr])

# debit : jetons de sortie par seconde, sur les libres
debit = st.median([r["tokens_sortie"] / r["secondes"] for r in li if r["secondes"] > 1])
print("calibration : %.2f car./jeton    debit median %.1f jetons/s" % (ratio, debit))
print("population : %d libres + %d tronques = %d appels" % (len(li), len(tr), len(recs)))
print()

# longueur de PENSEE en jetons, pour les libres ; les tronques = infini
pensees = []
for r in li:
    pc = r.get("pensee_car")
    if pc and pc > 0:
        pensees.append(pc / ratio)
pensees.sort()
N = len(pensees) + len(tr)   # denominateur = tous les appels

print("=== DISTRIBUTION DE LA PENSEE (jetons) ===")
for q in (25, 50, 75, 90, 95):
    print("  p%-3d : %6d" % (q, pensees[int(q / 100.0 * len(pensees))]))
print("  + %d appels au-dela de tout barreau (les fuites)" % len(tr))
print()

BARREAUX = (4096, 8192, 12288, 16384, 24576, 32768)
print("=== TAUX D'ESCALADE PAR BARREAU ===")
print("%9s %10s %12s" % ("barreau", "escalade", "cout du barreau"))
esc = {}
for b in BARREAUX:
    depasse = sum(1 for p in pensees if p > b) + len(tr)
    esc[b] = depasse / N
    # cout moyen d'un appel a ce barreau : min(pensee, b) jetons
    jetons = [min(p, b) for p in pensees] + [b] * len(tr)
    cout = sum(jetons) / len(jetons) / debit
    print("%9d %9.1f %% %10.0f s" % (b, 100 * esc[b], cout))
print()

def cout_echelle(barreaux):
    """cout total moyen par question d'une echelle : on paie chaque barreau
    atteint, du plus bas jusqu'a celui qui suffit (pas de reprise possible)."""
    total = 0.0
    for i, b in enumerate(barreaux):
        # part des questions qui ARRIVENT a ce barreau
        part = 1.0 if i == 0 else esc[barreaux[i - 1]]
        jetons = [min(p, b) for p in pensees] + [b] * len(tr)
        total += part * (sum(jetons) / len(jetons)) / debit
    return total

print("=== COUT TOTAL PAR QUESTION, ECHELLE CONTRE BARREAU UNIQUE ===")
SCENARIOS = [
    ("libre 32768 (le bras actuel)", None),
    ("barreau unique 24576", [24576]),
    ("echelle 8192 -> 24576", [8192, 24576]),
    ("echelle 16384 -> 32768", [16384, 32768]),
    ("echelle 8192 -> 16384 -> 32768", [8192, 16384, 32768]),
    ("echelle 4096 -> 12288 -> 32768", [4096, 12288, 32768]),
]
reel = sum(r["secondes"] for r in recs) / len(recs)
print("  %-34s %8.0f s / question   (mesure directe)" % (SCENARIOS[0][0], reel))
for nom, b in SCENARIOS[1:]:
    print("  %-34s %8.0f s / question   reste non conclu : %.1f %%"
          % (nom, cout_echelle(b), 100 * esc[b[-1]]))
print()
print("  Lecture : « reste non conclu » = part des questions qui butent encore")
print("  sur le DERNIER barreau. Une echelle ne supprime pas les fuites, elle")
print("  les rend moins cheres -- et elle FORCE une reponse a chaque barreau.")
