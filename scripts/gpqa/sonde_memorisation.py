# -*- coding: utf-8 -*-
"""Sonde de memorisation : le modele a-t-il vu Exercism en pre-entrainement ?

POURQUOI CETTE SONDE, ET PAS UNE MESURE DE SIMILARITE DE PLUS

La similarite entre la solution ecrite et le corrige canonique (mesuree le
26/08 sur le run aider aveugle : mediane 11,5 %, zero cas au-dessus de 80 %)
elimine la REGURGITATION VERBATIM du corrige. Elle n'elimine pas la
memorisation de l'enonce, du fichier de test, ou d'une des milliers de
solutions communautaires. Cette sonde attaque le point le plus dur a
expliquer autrement : le FICHIER DE TEST.

Un fichier de test Exercism contient des VALEURS LITTERALES ARBITRAIRES --
les entrees et sorties attendues de chaque cas. Elles ne se deduisent pas de
l'enonce. Un modele qui, a partir des 40 premiers pour cent du fichier,
restitue la suite avec ses valeurs exactes ne raisonne pas : il se souvient.

LE CONTROLE, SANS LEQUEL LA SONDE NE PROUVE RIEN

Les fichiers de test se ressemblent : meme cadre, meme forme d'assertion. Une
similarite elevee pourrait donc n'etre que de la completion syntaxique. D'ou
deux bras sur LE MEME fichier :

  A. REEL     : le prefixe tel quel. Le modele peut reconnaitre l'exercice.
  B. ANONYME  : le meme prefixe, meme structure, memes valeurs, mais tous les
                noms identifiant l'exercice remplaces par des neutres. La
                syntaxe et la difficulte de completion sont inchangees ; seule
                l'ETIQUETTE qui permettrait le rappel a disparu.

La cible est renommee de la meme facon dans le bras B : on compare bien la
meme tache. Lecture :

  A >> B  -> le modele s'appuie sur l'identite de l'exercice : RAPPEL.
  A ~= B  -> il complete de la syntaxe : pas de preuve de memorisation.

Une similarite floue seule se discute ; on rapporte donc aussi le RAPPEL DE
LIGNES EXACTES -- combien de lignes non triviales de la suite reelle sont
restituees mot pour mot. C'est ce chiffre-la qui est difficile a expliquer
autrement que par la memorisation.
"""
import argparse
import difflib
import glob
import io
import json
import os
import re
import sys
import threading
import time
from concurrent import futures

import requests

CORPUS = (r"C:\Users\test\tools\aider-bench\aider\tmp.benchmarks"
          r"\polyglot-benchmark")

NEUTRES = ["widget", "Widget", "WIDGET", "widgetOps", "widget_ops"]

GABARIT = """Here is the beginning of a unit-test file from a coding exercise.

Continue the file. Output ONLY the remaining code, with no explanation, no
markdown fences, and no repetition of the part already shown.

```{lang}
{prefixe}
```"""

COMMENTAIRE = {".py": r"#.*", ".rs": r"//.*", ".go": r"//.*", ".js": r"//.*",
               ".cpp": r"//.*", ".h": r"//.*", ".java": r"//.*"}
LANG_MD = {".py": "python", ".rs": "rust", ".go": "go", ".js": "javascript",
           ".cpp": "cpp", ".java": "java"}


def normaliser(texte, ext):
    motif = COMMENTAIRE.get(ext)
    if motif:
        texte = re.sub(motif, "", texte)
    texte = re.sub(r"/\*.*?\*/", "", texte, flags=re.S)
    return re.sub(r"\s+", "", texte)


def variantes_du_nom(ex):
    """Graphies du nom de l'exercice, chacune avec son neutre DE MEME STYLE.

    Le remplacement doit garder le fichier COHERENT : si `all_your_base.h`
    devient `WIDGET.h` mais que la classe `AllYourBase` devient autre chose,
    les references internes ne se repondent plus. Le bras anonyme serait alors
    plus dur a completer pour une raison qui n'a rien a voir avec l'identite
    de l'exercice -- et l'ecart A-B serait gonfle par un artefact.

    Rendu trie de la PLUS LONGUE graphie a la plus courte : substituer `base`
    avant `all_your_base` couperait la seconde en morceaux.
    """
    mots = [m for m in re.split(r"[-_]", ex) if m]
    if len(mots) == 1:
        # DEFAUT CORRIGE LE 26/08. Avec un nom d'un seul mot, les sept graphies
        # ci-dessous s'effondrent sur LA MEME cle de dictionnaire et Python
        # gardait la derniere : `diamond` -> `widget ops`, AVEC UNE ESPACE.
        # Le bras anonyme recevait alors `#include "widget ops.h"` et
        # `widget ops::rows(...)` -- du code qui ne compile pas. Il devenait
        # plus dur pour une raison SANS RAPPORT avec l'identite de l'exercice,
        # et l'ecart A-B mesurait ma substitution, pas la memorisation :
        # sur les 26 exercices touches l'ecart etait +7,8 pt (z = 2,12), sur
        # les 34 sains +1,1 pt (z = 0,57). Un nom d'un mot recoit donc un
        # neutre d'un mot.
        paires = {ex: "widget", ex.capitalize(): "Widget", ex.upper(): "WIDGET"}
    else:
        paires = {
            ex:                                        "widget-ops",
            ex.replace("-", "_"):                      "widget_ops",
            ex.replace("-", ""):                       "widgetops",
            "".join(m.capitalize() for m in mots):     "WidgetOps",
            mots[0] + "".join(m.capitalize() for m in mots[1:]): "widgetOps",
            "_".join(mots).upper():                    "WIDGET_OPS",
            ex.replace("-", " "):                      "widget ops",
        }
    sortie = sorted(((k, v) for k, v in paires.items() if k),
                    key=lambda kv: len(kv[0]), reverse=True)
    # INVARIANT DE FORME. Une graphie sans espace doit recevoir un neutre sans
    # espace, sinon on casse un identifiant. C'est le controle exact qui aurait
    # arrete le defaut ci-dessus avant de depenser 120 appels.
    for graphie, neutre in sortie:
        if " " not in graphie and " " in neutre:
            raise SystemExit(
                "REFUS : la graphie %r recevrait le neutre %r qui contient une "
                "espace ; la substitution casserait un identifiant et le bras "
                "anonyme serait plus dur pour une raison etrangere a la "
                "memorisation." % (graphie, neutre))
    return sortie


def anonymiser(texte, ex):
    """Remplace toute graphie du nom de l'exercice par son neutre de meme style."""
    for graphie, neutre in variantes_du_nom(ex):
        texte = texte.replace(graphie, neutre)
    return texte


def couper(texte, part=0.4):
    lignes = texte.split("\n")
    n = max(3, int(len(lignes) * part))
    return "\n".join(lignes[:n]), "\n".join(lignes[n:])


def lignes_utiles(texte):
    """Lignes assez specifiques pour qu'une restitution exacte compte.

    On ecarte les lignes courtes, les accolades seules et les fermetures : les
    restituer ne prouve rien.
    """
    out = []
    for l in texte.split("\n"):
        s = l.strip()
        if len(s) >= 20 and not re.fullmatch(r"[}\)\];,\s]*", s):
            out.append(s)
    return out


def interroger(url, cle, modele, prompt, max_tokens, delai, extra):
    corps = {"model": modele, "temperature": 0.0, "max_tokens": max_tokens,
             "messages": [{"role": "user", "content": prompt}]}
    corps.update(extra or {})
    e = {"Content-Type": "application/json"}
    if cle:
        e["Authorization"] = "Bearer %s" % cle
    r = requests.post(url.rstrip("/") + "/chat/completions", headers=e,
                      json=corps, timeout=delai)
    r.raise_for_status()
    d = r.json()
    ch = (d.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    txt = msg.get("content") or ""
    txt = re.sub(r"^\s*```[a-zA-Z+]*\s*|\s*```\s*$", "", txt.strip())
    return {"texte": txt,
            "fournisseur": d.get("provider"),
            "tokens_sortie": (d.get("usage") or {}).get("completion_tokens"),
            "finish_reason": ch.get("finish_reason"),
            "tokens_raisonnement": len(msg.get("reasoning") or "") // 4 or None}


def charger_dotenv(chemin):
    n = 0
    for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$",
                     ligne)
        if m:
            os.environ.setdefault(
                m.group(1), m.group(2).strip().strip('"').strip("'"))
            n += 1
    return n


def temoins(par_langue):
    """N exercices par langage, avec leur plus gros fichier de test."""
    out = []
    for lang in sorted(os.listdir(CORPUS)):
        d = os.path.join(CORPUS, lang, "exercises", "practice")
        if not os.path.isdir(d):
            continue
        pris = 0
        for ex in sorted(os.listdir(d)):
            if pris >= par_langue:
                break
            cfg = os.path.join(d, ex, ".meta", "config.json")
            if not os.path.exists(cfg):
                continue
            tests = json.loads(io.open(cfg, encoding="utf-8").read()).get(
                "files", {}).get("test", [])
            plus_gros, taille, ext = None, 0, ""
            for t in tests:
                p = os.path.join(d, ex, t.replace("/", os.sep))
                if not os.path.exists(p):
                    continue
                s = io.open(p, encoding="utf-8", errors="replace").read()
                if len(s) > taille:
                    plus_gros, taille, ext = s, len(s), os.path.splitext(t)[1]
            if plus_gros and taille >= 800:
                out.append({"lang": lang, "ex": ex, "texte": plus_gros,
                            "ext": ext})
                pris += 1
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("sortie", default="sonde_memo.jsonl", nargs="?")
    p.add_argument("--url", default="https://openrouter.ai/api/v1")
    p.add_argument("--modele", default="qwen/qwen3.8-27b")
    p.add_argument("--dotenv",
                   default=r"C:\Users\test\Documents\dsh2.0\.env")
    p.add_argument("--cle-env", default="OPENROUTER_API_KEY")
    p.add_argument("--par-langue", type=int, default=5)
    p.add_argument("--max-tokens", type=int, default=4000)
    p.add_argument("--raisonnement", action="store_true",
                   help="laisse le bloc de pensee actif (defaut : coupe)")
    p.add_argument("--parallele", type=int, default=8)
    p.add_argument("--delai", type=int, default=300)
    p.add_argument("--extra-fichier", default="extra_or_bf16.json")
    args = p.parse_args()

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True)
    print("%d variables chargees depuis .env (valeurs jamais affichees)"
          % charger_dotenv(args.dotenv))
    cle = os.environ.get(args.cle_env)
    if not cle:
        raise SystemExit("REFUS : %s absente." % args.cle_env)
    extra = {}
    if args.extra_fichier and os.path.exists(args.extra_fichier):
        extra = json.loads(io.open(args.extra_fichier, encoding="utf-8").read())
        extra.pop("top_k", None)   # temperature 0 : pas d'echantillonnage
        extra.pop("min_p", None)
    if not args.raisonnement:
        # La tache est une COMPLETION, pas un raisonnement : le modele doit
        # ecrire la suite du fichier, pas deliberer. Laisser le bloc de pensee
        # actif lui fait consommer tout le budget avant d'avoir ecrit un
        # caractere (mesure le 26/08 : 59 sorties vides sur 60). La coupure
        # s'applique IDENTIQUEMENT aux deux bras, elle ne peut donc pas creuser
        # ni combler l'ecart A-B qui est la mesure.
        extra["reasoning"] = {"enabled": False}

    lot = temoins(args.par_langue)
    print("temoins : %d exercices (%d par langage max)"
          % (len(lot), args.par_langue))
    print("modele : %s   extra : %s" % (args.modele, extra))
    print("")

    f = io.open(args.sortie, "a", encoding="utf-8")
    verrou = threading.Lock()
    t0 = time.time()
    taches = [(t, bras) for t in lot for bras in ("reel", "anonyme")]

    def traiter(tache):
        t, bras = tache
        texte = t["texte"] if bras == "reel" else anonymiser(t["texte"], t["ex"])
        prefixe, suite = couper(texte)
        prompt = GABARIT.format(lang=LANG_MD.get(t["ext"], ""), prefixe=prefixe)
        enreg = {"lang": t["lang"], "ex": t["ex"], "bras": bras,
                 "ext": t["ext"]}
        try:
            rep = interroger(args.url, cle, args.modele, prompt,
                             args.max_tokens, args.delai, extra)
        except Exception as e:
            enreg["erreur"] = "%s: %s" % (type(e).__name__, str(e)[:200])
            with verrou:
                f.write(json.dumps(enreg, ensure_ascii=False) + "\n"); f.flush()
                print("  ERREUR %-28s %-8s %s"
                      % (t["ex"][:28], bras, enreg["erreur"][:70]))
            return
        sortie, fournisseur, tok = (rep["texte"], rep["fournisseur"],
                                    rep["tokens_sortie"])
        enreg["finish_reason"] = rep["finish_reason"]

        # GARDE-FOU. Une reponse VIDE n'est pas une similarite de zero : c'est
        # une absence de mesure. Le 26/08, 59 appels sur 60 ont epuise les 3000
        # tokens dans le bloc de raisonnement et rendu un contenu vide ; les
        # comptabiliser a 0 % aurait donne un "A = B = 0, aucune memorisation"
        # entierement fabrique. On les marque et le depouillement les EXCLUT.
        if not sortie.strip():
            enreg.update({"non_mesure": "sortie vide (finish_reason=%s, %s "
                                        "tokens)" % (rep["finish_reason"], tok),
                          "tokens_sortie": tok, "fournisseur": fournisseur})
            with verrou:
                f.write(json.dumps(enreg, ensure_ascii=False) + "\n"); f.flush()
                print("  NON-MESURE %-6s %-4s %-24s sortie vide (%s, %s tok)"
                      % (t["lang"], bras[:4], t["ex"][:24],
                         rep["finish_reason"], tok))
            return

        na, nb = normaliser(sortie, t["ext"]), normaliser(suite, t["ext"])
        simil = difflib.SequenceMatcher(None, na, nb).ratio() if nb else 0.0
        vraies = lignes_utiles(suite)
        rendues = set(lignes_utiles(sortie))
        exactes = sum(1 for l in vraies if l in rendues)
        enreg.update({
            "similarite": round(simil, 4),
            "lignes_utiles_attendues": len(vraies),
            "lignes_exactes": exactes,
            "rappel_lignes": round(exactes / len(vraies), 4) if vraies else 0.0,
            "tokens_sortie": tok, "fournisseur": fournisseur,
            "sortie": sortie[:3000],
        })
        with verrou:
            f.write(json.dumps(enreg, ensure_ascii=False) + "\n"); f.flush()
            print("  %-6s %-4s %-26s simil %5.1f %%   lignes exactes %3d/%-3d "
                  "(%5.1f %%)  [%.1f min]"
                  % (t["lang"], bras[:4], t["ex"][:26], 100 * simil, exactes,
                     len(vraies), 100 * enreg["rappel_lignes"],
                     (time.time() - t0) / 60))

    if args.parallele <= 1:
        for x in taches:
            traiter(x)
    else:
        with futures.ThreadPoolExecutor(max_workers=args.parallele) as ex:
            list(ex.map(traiter, taches))
    f.close()
    print("")
    print("depouillement : python depouiller_sonde.py %s" % args.sortie)


if __name__ == "__main__":
    main()
