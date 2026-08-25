#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pirt.py -- repli nocturne du registre PIRT (docs/PIRT.md, chantier 25/08).

OUTILLAGE OPEN : ce script ne contient AUCUNE donnee du framework. Les donnees
(phenomenes.yaml, evenements.jsonl, PIRT.md, pirt.sqlite) vivent dans le depot
framework, repertoire passe par --pirt. 0 LLM, 0 USD, CPU seul.

Contrat (D1) :
  - lit <pirt>/evenements.jsonl (source de verite, append-only, gabarit :
      {"date":"AAAA-MM-JJ","phenomene":"<id>","type":"audit_mutation",
       "donnees":{"constante":"X","bite":true,"echecs":9,"total":99,
                  "portee":"ancres"},"source":"reports/..."}
    types admis : audit_mutation | suite_promue | ancre | note_vv) ;
  - RECONSTRUIT <pirt>/pirt.sqlite a partir de zero (cache derive, jamais la
    source ; idempotence par construction : meme JSONL => meme base) ;
  - recalcule pirt_etat et regenere le bloc genere de <pirt>/PIRT.md
    (seul le bloc genere fait foi pour les comptes) ;
  - imprime le top-3 des cibles proposees (l'humain choisit).

Principes (docs/PIRT.md) :
  - importance : colonne HUMAINE (phenomenes.yaml), jamais calculee ici ;
    NULL = pas classe, trie en dernier.
  - fail-closed : une ligne JSONL invalide => exit 2, RIEN n'est ecrit.
  - couverture = constantes dont la DERNIERE mutation a mordu / constantes
    tentees (dernier evenement par (phenomene, constante) fait foi : un
    no-bite ferme par un renforcement prouve compte comme couvert).
  - portee du dernier bite : 'ancres' (propagation fonctionnelle) >
    'litteral' (seule l'assertion du litteral echoue) > 'aucune'.

Sorties : 0 repli fait (y compris « aucun changement ») ; 1 evenements.jsonl
absent ; 2 ligne invalide (rien ecrit) ; 3 erreur d'ecriture.

Residu accepte (red team D4, P7) : un exit 3 peut laisser pirt.sqlite ecrit et
PIRT.md non regenere -- les deux sont des DERIVES reconstruits au repli
suivant, l'etat se repare seul ; la source (JSONL) n'est jamais touchee.
"""
import argparse
import io
import json
import os
import sqlite3
import sys

TYPES = ("audit_mutation", "suite_promue", "ancre", "note_vv")
PORTEES = {"aucune": 0, "litteral": 1, "ancres": 2}
CONFIANCES = {"aucune": 0, "triage": 1, "validee": 2}
MARQUE_DEBUT = "<!-- PIRT:DEBUT (genere par harness/pirt.py -- ne pas editer ce bloc) -->"
MARQUE_FIN = "<!-- PIRT:FIN -->"


def lire_evenements(chemin):
    """Lit et valide TOUT le JSONL avant toute ecriture (fail-closed)."""
    evenements = []
    with io.open(chemin, encoding="utf-8") as f:
        for num, ligne in enumerate(f, 1):
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                e = json.loads(ligne)
            except json.JSONDecodeError as exc:
                print("evenements.jsonl ligne %d : JSON invalide (%s) -- rien n'est ecrit" % (num, exc))
                sys.exit(2)
            manquants = [c for c in ("date", "phenomene", "type", "donnees", "source") if c not in e]
            # Red team D4 (P2, 25/08) : un champ present mais VIDE passait la
            # validation structurelle -- exige des chaines non vides.
            vides = [c for c in ("date", "phenomene", "type", "source")
                     if c in e and (not isinstance(e[c], str) or not e[c].strip())]
            if manquants or vides or e["type"] not in TYPES or not isinstance(e["donnees"], dict):
                print("evenements.jsonl ligne %d : champs manquants/vides/invalides %s -- rien n'est ecrit"
                      % (num, manquants + vides or [e.get("type")]))
                sys.exit(2)
            e["_ordre"] = num
            evenements.append(e)
    return evenements


def lire_phenomenes(chemin):
    """phenomenes.yaml : id -> {module, fichier_source, description, importance}.
    importance est HUMAINE ; ce script la lit, ne l'ecrit jamais."""
    if not os.path.exists(chemin):
        return {}
    import yaml
    doc = yaml.safe_load(io.open(chemin, encoding="utf-8")) or []
    table = {}
    for p in doc:
        imp = p.get("importance")
        if imp is not None and imp not in (1, 2, 3):
            print("phenomenes.yaml : importance invalide %r pour %s (admis: 1..3 ou vide)" % (imp, p.get("id")))
            sys.exit(2)
        table[p["id"]] = {"module": p.get("module", ""), "fichier_source": p.get("fichier_source", ""),
                          "description": p.get("description", ""), "importance": imp,
                          "cree_le": str(p.get("cree_le", ""))}
    return table


def calculer_etat(evenements):
    """pirt_etat par phenomene, depuis les evenements seuls."""
    par_phen = {}
    for e in evenements:
        par_phen.setdefault(e["phenomene"], []).append(e)
    etats = {}
    for phen, evs in par_phen.items():
        evs = sorted(evs, key=lambda e: (e["date"], e["_ordre"]))
        # dernier evenement par constante mutee
        dernier_par_constante = {}
        for e in evs:
            if e["type"] == "audit_mutation":
                dernier_par_constante[e["donnees"].get("constante", "?")] = e
        tentees = len(dernier_par_constante)
        attrapees = sum(1 for e in dernier_par_constante.values() if e["donnees"].get("bite") is True)
        couverture = (attrapees / tentees) if tentees else 0.0
        bites = [e for e in evs if e["type"] == "audit_mutation" and e["donnees"].get("bite") is True]
        dernier_bite = bites[-1]["date"] if bites else ""
        portee = bites[-1]["donnees"].get("portee", "aucune") if bites else "aucune"
        if portee not in PORTEES:
            portee = "aucune"
        nb_tests = None
        for e in evs:
            if e["type"] == "suite_promue" and isinstance(e["donnees"].get("tests"), int):
                nb_tests = e["donnees"]["tests"]
        confiance = "aucune"
        for e in evs:
            if e["type"] == "note_vv" and e["donnees"].get("niveau") in CONFIANCES:
                confiance = e["donnees"]["niveau"]
        audits = [e for e in evs if e["type"] == "audit_mutation"]
        dernier_audit = ""
        if audits:
            d = audits[-1]["donnees"]
            total = d.get("total", (d.get("echecs", 0) + d.get("ok", 0)) or "?")
            dernier_audit = "%s/%s" % (d.get("echecs", "?"), total)
        etats[phen] = {"couverture": round(couverture, 4), "nb_tests": nb_tests,
                       "dernier_bite": dernier_bite, "portee": portee,
                       "confiance_vv": confiance, "dernier_audit": dernier_audit,
                       "nb_evenements": len(evs), "maj_le": evs[-1]["date"]}
    return etats


def cle_priorite(item, phenomenes):
    phen, etat = item
    imp = (phenomenes.get(phen) or {}).get("importance")
    # importance DESC (NULL dernier), couverture ASC, portee ASC, confiance ASC
    return (0 if imp is not None else 1, -(imp or 0), etat["couverture"],
            PORTEES[etat["portee"]], CONFIANCES[etat["confiance_vv"]], phen)


def ecrire_sqlite(chemin, phenomenes, evenements, etats):
    if os.path.exists(chemin):
        os.remove(chemin)  # cache DERIVE cree par ce script -- la source est le JSONL
    c = sqlite3.connect(chemin)
    c.executescript("""
CREATE TABLE phenomenes (id TEXT PRIMARY KEY, module TEXT, fichier_source TEXT,
  description TEXT, importance INTEGER, cree_le TEXT);
CREATE TABLE pirt_evenements (id INTEGER PRIMARY KEY AUTOINCREMENT,
  phenomene_id TEXT, date TEXT, type TEXT, donnees TEXT, source TEXT);
CREATE TABLE pirt_etat (phenomene_id TEXT PRIMARY KEY, couverture REAL,
  nb_tests INTEGER, dernier_bite TEXT, portee TEXT, confiance_vv TEXT, maj_le TEXT);
""")
    for pid, p in sorted(phenomenes.items()):
        c.execute("INSERT INTO phenomenes VALUES (?,?,?,?,?,?)",
                  (pid, p["module"], p["fichier_source"], p["description"], p["importance"], p["cree_le"]))
    for e in evenements:
        c.execute("INSERT INTO pirt_evenements (phenomene_id, date, type, donnees, source) VALUES (?,?,?,?,?)",
                  (e["phenomene"], e["date"], e["type"], json.dumps(e["donnees"], ensure_ascii=False), e["source"]))
    for phen, s in sorted(etats.items()):
        c.execute("INSERT INTO pirt_etat VALUES (?,?,?,?,?,?,?)",
                  (phen, s["couverture"], s["nb_tests"], s["dernier_bite"], s["portee"], s["confiance_vv"], s["maj_le"]))
    c.commit()
    c.close()


def generer_bloc(phenomenes, etats):
    lignes = [MARQUE_DEBUT, "",
              "| phenomene | importance | couverture | portee dernier bite | dernier audit (echecs/total) | tests suite | confiance V&V | evenements |",
              "|---|---|---|---|---|---|---|---|"]
    for phen, s in sorted(etats.items(), key=lambda kv: cle_priorite(kv, phenomenes)):
        imp = (phenomenes.get(phen) or {}).get("importance")
        lignes.append("| %s | %s | %.2f | %s | %s | %s | %s | %d |" % (
            phen, imp if imp is not None else "--", s["couverture"], s["portee"],
            s["dernier_audit"] or "--", s["nb_tests"] if s["nb_tests"] is not None else "--",
            s["confiance_vv"], s["nb_evenements"]))
    orphelins = sorted(set(phenomenes) - set(etats))
    for phen in orphelins:
        imp = phenomenes[phen].get("importance")
        lignes.append("| %s | %s | 0.00 | aucune | -- | -- | aucune | 0 |" % (phen, imp if imp is not None else "--"))
    lignes += ["",
               "Tri : importance DESC (non classe en dernier), couverture ASC, portee ASC,",
               "confiance ASC. `importance` n'est ecrite que par l'humain (phenomenes.yaml).",
               "", MARQUE_FIN]
    return "\n".join(lignes)


def ecrire_md(chemin, bloc):
    squelette = ("# PIRT -- registre vivant (donnees PRIVATE)\n\n"
                 "Source de verite : `evenements.jsonl` (append-only, gabarit dans\n"
                 "`harness/pirt.py` du depot dsh2.0). Ce fichier est REGENERE chaque nuit ;\n"
                 "seul le bloc genere fait foi pour les comptes.\n\n"
                 + bloc + "\n")
    if not os.path.exists(chemin):
        contenu = squelette
    else:
        actuel = io.open(chemin, encoding="utf-8").read()
        if MARQUE_DEBUT in actuel and MARQUE_FIN in actuel:
            avant = actuel.split(MARQUE_DEBUT)[0]
            apres = actuel.split(MARQUE_FIN, 1)[1]
            contenu = avant + bloc + apres
        else:
            contenu = actuel.rstrip() + "\n\n" + bloc + "\n"
    io.open(chemin, "w", encoding="utf-8", newline="\n").write(contenu)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pirt", required=True, help="repertoire pirt/ du depot framework (PRIVATE)")
    ap.add_argument("--sans-md", action="store_true", help="repli sqlite seul, sans regenerer PIRT.md")
    a = ap.parse_args()
    jsonl = os.path.join(a.pirt, "evenements.jsonl")
    if not os.path.exists(jsonl):
        print("evenements.jsonl absent sous %s -- rien a replier" % a.pirt)
        sys.exit(1)
    evenements = lire_evenements(jsonl)          # valide TOUT avant d'ecrire
    phenomenes = lire_phenomenes(os.path.join(a.pirt, "phenomenes.yaml"))
    etats = calculer_etat(evenements)
    try:
        ecrire_sqlite(os.path.join(a.pirt, "pirt.sqlite"), phenomenes, evenements, etats)
        if not a.sans_md:
            ecrire_md(os.path.join(a.pirt, "PIRT.md"), generer_bloc(phenomenes, etats))
    except OSError as exc:
        print("ECHEC ecriture : %s" % exc)
        sys.exit(3)
    tri = sorted(etats.items(), key=lambda kv: cle_priorite(kv, phenomenes))
    print("PIRT : %d evenements, %d phenomenes replies ; top-3 cibles proposees (l'humain choisit) :"
          % (len(evenements), len(etats)))
    for phen, s in tri[:3]:
        imp = (phenomenes.get(phen) or {}).get("importance")
        print("  - %s (importance=%s couverture=%.2f portee=%s confiance=%s)"
              % (phen, imp if imp is not None else "non classee", s["couverture"], s["portee"], s["confiance_vv"]))
    sys.exit(0)


if __name__ == "__main__":
    main()
