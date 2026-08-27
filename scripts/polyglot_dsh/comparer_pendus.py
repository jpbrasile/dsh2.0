# -*- coding: utf-8 -*-
"""AVANT / APRES sur les exercices rejoues apres la panne de pendaison.

CE QU'ON COMPARE. Trois exercices ont ete juges alors que le harnais pendait :
l'agent avait cesse d'appeler le modele et attendait la laisse, faute d'un
delai sur son outil `bash`. Deux autres ont ete amputes par un arret manuel.
Tous ont ete rejoues sous le harnais repare (`--veille-silence`).

LA REGLE ETAIT ECRITE AVANT LE REJEU : le verdict du rejeu est l'officiel,
quel qu'il soit. Ce depouillement ne choisit rien, il MONTRE les deux.

CE QU'IL NE FAUT PAS LUI FAIRE DIRE. Le banc echantillonne -- pas de graine,
temperature 1.0. Deux passages du meme exercice sous la MEME configuration
divergent deja (mesure du 27/08). Un basculement isole ne prouve donc rien
sur le correctif : il dit seulement quel verdict est officiel maintenant.
Ce qui est PROUVE, et qui ne depend d'aucun verdict, c'est le temps : un
tour pendu coutait la laisse entiere, un tour surveille rend la main.
"""
import argparse
import glob
import json
import os

RACINE = os.path.join(os.path.expanduser("~"),
                      "tools", "aider-bench", "aider", "tmp.benchmarks")


def lire(chemin):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def verdict(d):
    if not d:
        return None
    issues = d.get("tests_outcomes") or []
    if not issues:
        return "VIDE"
    return "PASS" if issues[-1] else "FAIL"


def silence_max(d):
    """Le plus long tour du journal, et s'il a ete coupe."""
    pire, coupe = 0.0, False
    for t in (d.get("turns") or []):
        s = float(t.get("secondes") or 0.0)
        if s > pire:
            pire, coupe = s, bool(t.get("coupe"))
    return pire, coupe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--horodatage", default="",
                    help="suffixe des resultats ecartes (.pendu-<horo>). "
                         "Vide = tous les .pendu-* trouves.")
    ap.add_argument("--langage", default="cpp")
    a = ap.parse_args()

    prat = os.path.join(RACINE, a.run, a.langage, "exercises", "practice")
    motif = ".dsh.results.json.pendu-%s" % (a.horodatage or "*")

    lignes = []
    for ex in sorted(os.listdir(prat)):
        d = os.path.join(prat, ex)
        if not os.path.isdir(d):
            continue
        vieux = sorted(glob.glob(os.path.join(d, motif)))
        neuf = lire(os.path.join(d, ".dsh.results.json"))
        if not vieux and not neuf:
            continue
        if not vieux:
            continue                      # exercice ordinaire, pas concerne
        av = lire(vieux[-1])
        lignes.append((ex, av, neuf))

    if not lignes:
        print("aucun exercice ecarte ne correspond a %s" % motif)
        return

    print("AVANT (harnais pendu) / APRES (harnais repare) -- run %s" % a.run)
    print("")
    print("%-26s %-18s %-18s %s" % ("exercice", "AVANT", "APRES", "temps"))
    print("-" * 88)
    bascule = []
    gagne = 0.0
    for ex, av, ap_ in lignes:
        va, vn = verdict(av), verdict(ap_)
        pa, ca = silence_max(av) if av else (0.0, False)
        pn, cn = silence_max(ap_) if ap_ else (0.0, False)
        da = float((av or {}).get("duration") or 0.0)
        dn = float((ap_ or {}).get("duration") or 0.0)
        if ap_ is None:
            vn, dn = "(pas rejoue)", 0.0
        else:
            gagne += (da - dn)
        if va and vn and va != vn and ap_ is not None:
            bascule.append((ex, va, vn))
        print("%-26s %-4s %6.1fs%-6s %-4s %6.1fs%-6s %+7.1fs"
              % (ex,
                 va, da, " COUPE" if ca else "",
                 vn, dn, " COUPE" if cn else "",
                 (dn - da) if ap_ is not None else 0.0))

    print("")
    print("=== LECTURE ===")
    if bascule:
        print("verdicts qui basculent (%d) :" % len(bascule))
        for ex, va, vn in bascule:
            print("   %-26s %s -> %s   <- le rejeu fait foi, regle ecrite "
                  "avant" % (ex, va, vn))
        print("")
        print("NE PAS attribuer ces basculements au correctif : le banc")
        print("echantillonne (temperature 1.0, aucune graine), deux passages")
        print("de la meme configuration divergent deja. Le correctif se juge")
        print("sur le TEMPS, pas sur les verdicts.")
    else:
        print("aucun verdict ne bascule.")
    print("")
    print("temps de paroi : %+.0f s au total (%+.1f h) sur %d exercices"
          % (-gagne, -gagne / 3600.0, len(lignes)))


if __name__ == "__main__":
    main()
