"""COMBIEN DE CONTEXTE UN APPEL DU POLYGLOT DEMANDE-T-IL VRAIMENT ?

La question pratique : `--parallel N` decoupe `--ctx-size` en N tranches
(`n_ctx_slot = n_ctx / n_parallel`). Il faut donc savoir quelle tranche suffit.
On le lit sur le journal du proxy, pas sur une intuition.
"""
import json, os, glob, statistics as st

BANC = os.path.join(os.environ["USERPROFILE"], "Documents", "dsh2.0",
                    "scripts", "bench_julia_effort")

for chemin in sorted(glob.glob(os.path.join(BANC, "wire_pi_dim*.jsonl"))):
    entrees, sorties = [], []
    for ligne in open(chemin, encoding="utf-8", errors="ignore"):
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            r = json.loads(ligne)
        except Exception:
            continue
        u = r.get("usage") or {}
        pi = u.get("prompt_tokens")
        po = u.get("completion_tokens")
        if pi:
            entrees.append(pi)
        if po:
            sorties.append(po)
    print("== %s : %d appels avec usage" % (os.path.basename(chemin), len(entrees)))
    if not entrees:
        # pas d'usage : replier sur la taille des messages
        continue
    for nom, v in (("invite (jetons)", entrees), ("sortie (jetons)", sorties)):
        if not v:
            continue
        v = sorted(v)
        print("   %-18s p50 %6d   p90 %6d   max %6d"
              % (nom, v[len(v) // 2], v[int(0.9 * len(v))], v[-1]))
    # ce qui compte pour le slot : invite + sortie du meme appel, majore
    print("   pic contexte majore (max invite + max sortie) : %d jetons"
          % (max(entrees) + (max(sorties) if sorties else 0)))
