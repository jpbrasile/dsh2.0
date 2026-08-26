#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GPQA Diamond sur un serveur OpenAI-compatible -- local ou distant.

Le meme harnais des deux cotes. C'est tout l'interet : un score GPQA publie
n'est pas opposable a un score maison, parce que le gabarit de prompt,
l'extraction de la reponse et le reglage CoT deplacent le resultat de
plusieurs points. Un ecart Q4 / pleine precision ne veut dire quelque chose
que si les deux passent par le meme code.

Deux choix de mesure, tous deux declares :

1. ROTATIONS. Chaque question est posee 4 fois, la bonne reponse occupant
   tour a tour A, B, C, D. Les distracteurs tournent avec elle. Deux effets :
   le biais de position disparait exactement de l'agregat (et se mesure, cf.
   la table par position), et n passe de 198 a 792, ce qui ramene 1 sigma
   binomial de ~3,6 a ~1,8 point a 50 %. Sans ca, l'ecart qu'on cherche est
   sous le bruit.

2. ORDRE DES QUESTIONS BRASSE (graine fixe), les 4 rotations d'une question
   restant groupees. Consequence : un run interrompu reste un echantillon
   aleatoire non biaise ET equilibre en position. Un run partiel se lit.

Reprise : chaque appel est ecrit en JSONL au fil de l'eau ; relancer saute
les couples (Record ID, rotation) deja presents. Rien ne se perd sur un
plantage, et le fichier est la seule source de verite du depouillement.
"""
import argparse
import csv
import io
import json
import os
import random
import re
import sys
import threading
import time
from concurrent import futures

import requests

LETTRES = ("A", "B", "C", "D")

# Gabarit simple-evals (OpenAI) : c'est le plus repandu dans les chiffres
# publies. On le fige ici pour que les deux cotes de la comparaison le
# partagent -- pas parce qu'il serait meilleur.
GABARIT = """Answer the following multiple choice question. The last line of your response should be of the following format: 'Answer: $LETTER' (without quotes) where LETTER is one of ABCD. Think step by step before answering.

{question}

A) {a}
B) {b}
C) {c}
D) {d}"""

# Extraction. L'ordre compte : la forme demandee d'abord, les rattrapages
# ensuite. Tout ce qui echappe aux trois est compte NON PARSE et rapporte --
# jamais devine, jamais compte faux par defaut.
MOTIFS = [
    re.compile(r"Answer\s*:\s*\(?\*{0,2}([ABCD])\*{0,2}\)?", re.IGNORECASE),
    re.compile(r"\bfinal answer\b[^ABCD]{0,20}\(?([ABCD])\)?", re.IGNORECASE),
    re.compile(r"(?:^|\n)\s*\**\s*\(?([ABCD])\)?\s*\**\s*\.?\s*$"),
]

RE_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def normaliser(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def lire_csv(chemin):
    with io.open(chemin, encoding="utf-8", newline="") as f:
        lignes = list(csv.DictReader(f))
    items = []
    for i, r in enumerate(lignes):
        q = normaliser(r.get("Question"))
        bonne = normaliser(r.get("Correct Answer"))
        faux = [normaliser(r.get("Incorrect Answer %d" % k)) for k in (1, 2, 3)]
        if not q or not bonne or not all(faux):
            continue
        items.append({
            "id": (r.get("Record ID") or "ligne-%d" % i).strip(),
            "question": q,
            "bonne": bonne,
            "faux": faux,
            "domaine": normaliser(r.get("High-level domain")
                                  or r.get("Subdomain") or "?"),
            "sous_domaine": normaliser(r.get("Subdomain") or "?"),
        })
    return items


def rotations(item, graine):
    """4 presentations : la bonne reponse en A, puis B, puis C, puis D.

    Les distracteurs sont d'abord melanges (graine derivee de l'id, donc
    reproductible d'un run a l'autre et d'un serveur a l'autre), puis inseres
    dans l'ordre autour de la position visee.
    """
    rng = random.Random("%s|%d" % (item["id"], graine))
    faux = list(item["faux"])
    rng.shuffle(faux)
    out = []
    for pos in range(4):
        choix = list(faux)
        choix.insert(pos, item["bonne"])
        out.append({"rotation": pos, "choix": choix, "attendu": LETTRES[pos]})
    return out


def extraire(texte):
    sans_think = RE_THINK.sub(" ", texte or "")
    queue = sans_think[-2000:]
    for motif in MOTIFS:
        m = None
        for m in motif.finditer(queue):
            pass  # on garde la DERNIERE occurrence : le modele se corrige
        if m:
            return m.group(1).upper()
    return None


def interroger(url, cle, modele, prompt, temperature, top_p, max_tokens,
               delai, extra):
    corps = {
        "model": modele,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
    }
    corps.update(extra or {})
    entetes = {"Content-Type": "application/json"}
    if cle:
        entetes["Authorization"] = "Bearer %s" % cle
    t0 = time.time()
    r = requests.post(url.rstrip("/") + "/chat/completions",
                      headers=entetes, json=corps, timeout=delai)
    secondes = time.time() - t0
    r.raise_for_status()
    d = r.json()
    ch = (d.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    texte = msg.get("content") or ""
    raison = msg.get("reasoning_content") or msg.get("reasoning") or ""
    usage = d.get("usage") or {}
    return {
        "texte": texte,
        "raisonnement": raison,
        "finish_reason": ch.get("finish_reason"),
        "tokens_sortie": usage.get("completion_tokens"),
        "tokens_entree": usage.get("prompt_tokens"),
        "secondes": secondes,
        # OpenRouter renvoie le fournisseur qui a REELLEMENT servi l'appel.
        # On l'enregistre a chaque ligne : epingler un fournisseur bf16 dans
        # la requete ne prouve rien, seule la reponse le prouve. Un run ou
        # ce champ varie n'est pas une mesure de precision pleine.
        "fournisseur": d.get("provider"),
    }


def charger_dotenv(chemin):
    """Pose les variables du .env dans l'environnement du processus.

    N'ecrit RIEN : ni la valeur, ni un extrait, ni sa presence dans un
    journal. Une cle qui transite par une sortie standard finit dans un
    fichier de log, et un log finit dans un commit.
    """
    n = 0
    for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$",
                     ligne)
        if not m:
            continue
        os.environ.setdefault(m.group(1),
                              m.group(2).strip().strip('"').strip("'"))
        n += 1
    return n


def deja_fait(chemin):
    vus = set()
    if not os.path.exists(chemin):
        return vus
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                d = json.loads(ligne)
            except Exception:
                continue
            if d.get("erreur"):
                continue
            # Un appel TRONQUE (budget de reflexion epuise avant la reponse)
            # est enregistre comme un appel reussi a reponse nulle. Sans cette
            # clause, relancer avec un plafond plus haut le sauterait en
            # silence -- et le taux de non-parse resterait fige pour la
            # mauvaise raison. Mesure du 26/08 : 5 cas sur 49 en bf16, tous a
            # exactement max_tokens.
            if d.get("finish_reason") == "length" and not d.get("donne"):
                continue
            vus.add((d.get("id"), d.get("rotation")))
    return vus


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sortie", help="fichier JSONL des reponses (reprise auto)")
    p.add_argument("--csv", default="gpqa_diamond.csv")
    p.add_argument("--url", default="http://127.0.0.1:8005/v1")
    p.add_argument("--modele", default="specdec-q38-dflash2")
    p.add_argument("--dotenv", default=None,
                   help="fichier .env a charger dans l'environnement "
                        "avant de lire --cle-env. La valeur n'est ni "
                        "affichee, ni journalisee, ni recopiee.")
    p.add_argument("--cle-env", default=None,
                   help="NOM de la variable d'environnement portant la cle "
                        "(jamais la cle elle-meme sur la ligne de commande)")
    p.add_argument("--rotations", type=int, default=4, choices=(1, 2, 3, 4))
    p.add_argument("--questions", type=int, default=0,
                   help="0 = toutes ; sinon les N premieres de l'ordre brasse")
    p.add_argument("--temperature", type=float, default=0.6)
    p.add_argument("--top-p", type=float, default=0.95)
    p.add_argument("--max-tokens", type=int, default=16384)
    p.add_argument("--delai", type=int, default=900)
    p.add_argument("--graine", type=int, default=1234)
    p.add_argument("--parallele", type=int, default=1,
                   help="appels simultanes. 1 pour le local (une seule carte : "
                        "la concurrence n'y gagne rien et fausse les temps par "
                        "appel) ; >1 pour un service distant.")
    p.add_argument("--extra-fichier", default=None,
                   help="fichier JSON fusionne dans le corps de la requete. "
                        "PAS d'option --extra en ligne de commande : PowerShell "
                        "mange les guillemets d'un JSON inline (mesure du "
                        "26/08, '{\\\"top_k\\\": 20}' est arrive coupe en deux "
                        "arguments). Un JSON passe par un fichier, jamais par "
                        "un argument shell.")
    args = p.parse_args()

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True)

    if args.dotenv:
        print("%d variables chargees depuis %s (valeurs jamais affichees)"
              % (charger_dotenv(args.dotenv), args.dotenv))
    cle = os.environ.get(args.cle_env) if args.cle_env else None
    if args.cle_env and not cle:
        raise SystemExit("REFUS : la variable %s est absente de "
                         "l'environnement." % args.cle_env)
    extra = None
    if args.extra_fichier:
        extra = json.loads(io.open(args.extra_fichier, encoding="utf-8").read())

    items = lire_csv(args.csv)
    if len(items) != 198:
        print("ATTENTION : %d questions lues, 198 attendues pour Diamond"
              % len(items))
    random.Random(args.graine).shuffle(items)
    if args.questions:
        items = items[:args.questions]

    vus = deja_fait(args.sortie)
    total = len(items) * args.rotations
    print("GPQA Diamond -- %d questions x %d rotations = %d appels"
          % (len(items), args.rotations, total))
    print("modele : %s   url : %s" % (args.modele, args.url))
    print("temperature %.2f  top_p %.2f  max_tokens %d  extra %s"
          % (args.temperature, args.top_p, args.max_tokens, extra))
    if vus:
        print("reprise : %d appels deja en place, ils seront sautes" % len(vus))
    print("")

    # --- liste de travail, puis execution sequentielle ou en parallele ---
    # Le local se fait en sequentiel (--parallele 1) : une seule carte, la
    # concurrence n'y gagne rien et fausse les temps par appel. Le distant se
    # fait en parallele -- c'est la raison d'etre du reglage du harnais sur
    # OpenRouter : des minutes au lieu d'heures de carte.
    taches = []
    for item in items:
        for rot in rotations(item, args.graine)[:args.rotations]:
            if (item["id"], rot["rotation"]) not in vus:
                taches.append((item, rot))

    f = io.open(args.sortie, "a", encoding="utf-8")
    verrou = threading.Lock()
    etat = {"faits": 0, "bons": 0, "rates": 0}
    t0 = time.time()

    def traiter(tache):
        item, rot = tache
        prompt = GABARIT.format(question=item["question"],
                                a=rot["choix"][0], b=rot["choix"][1],
                                c=rot["choix"][2], d=rot["choix"][3])
        enreg = {"id": item["id"], "rotation": rot["rotation"],
                 "attendu": rot["attendu"], "domaine": item["domaine"],
                 "sous_domaine": item["sous_domaine"],
                 "modele": args.modele}
        try:
            rep = interroger(args.url, cle, args.modele, prompt,
                             args.temperature, args.top_p,
                             args.max_tokens, args.delai, extra)
        except Exception as e:
            enreg["erreur"] = "%s: %s" % (type(e).__name__, str(e)[:300])
            with verrou:
                f.write(json.dumps(enreg, ensure_ascii=False) + "\n")
                f.flush()
                etat["rates"] += 1
                print("  ERREUR %-24s rot %d  %s"
                      % (item["id"][:24], rot["rotation"],
                         enreg["erreur"][:90]))
            return
        donne = extraire(rep["texte"] or rep["raisonnement"])
        enreg.update({
            "donne": donne,
            "juste": bool(donne) and donne == rot["attendu"],
            "finish_reason": rep["finish_reason"],
            "tokens_sortie": rep["tokens_sortie"],
            "tokens_entree": rep["tokens_entree"],
            "secondes": round(rep["secondes"], 2),
            "fournisseur": rep.get("fournisseur"),
            # 4000 -> 24000 le 26/08. La coupe a 4000 emportait le `<think>`
            # OUVRANT des reponses longues : on lisait « aucun bloc de pensee »
            # sur des appels qui en avaient un de 16 000 jetons, et le debut du
            # champ commencait en plein calcul. La notation n'etait PAS touchee
            # (`extraire` travaille sur rep["texte"] complet, avant stockage),
            # mais toute analyse du raisonnement l'etait. 24000 caracteres
            # couvrent ~8000 jetons, au-dela du budget de pensee pose.
            "reponse": (rep["texte"] or "")[-24000:],
        })
        with verrou:
            f.write(json.dumps(enreg, ensure_ascii=False) + "\n")
            f.flush()
            etat["faits"] += 1
            if enreg["juste"]:
                etat["bons"] += 1
            print("  %4d/%-4d  %-26s rot %d  attendu %s  donne %-4s %s  "
                  "%5.0fs  %s tok  [%.1f %% | %.1f h ecoulees]"
                  % (etat["faits"], len(taches), item["id"][:26],
                     rot["rotation"], rot["attendu"], donne or "NON-PARSE",
                     "OK " if enreg["juste"] else "   ",
                     rep["secondes"], rep["tokens_sortie"],
                     100.0 * etat["bons"] / etat["faits"],
                     (time.time() - t0) / 3600.0))

    if args.parallele <= 1:
        for tache in taches:
            traiter(tache)
    else:
        with futures.ThreadPoolExecutor(max_workers=args.parallele) as ex:
            list(ex.map(traiter, taches))
    f.close()
    faits, bons, rates = etat["faits"], etat["bons"], etat["rates"]
    print("")
    print("appels effectues : %d   erreurs : %d" % (faits, rates))
    if faits:
        print("justes sur ce lot : %d/%d = %.1f %%"
              % (bons, faits, 100.0 * bons / faits))
    print("depouillement complet : python depouiller_gpqa.py %s" % args.sortie)


if __name__ == "__main__":
    main()
