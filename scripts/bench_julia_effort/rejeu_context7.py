# -*- coding: utf-8 -*-
"""Rejoue les requetes REELLEMENT parties du banc a travers Context7.

Pourquoi ce script existe : le banc paie OpenRouter pour chercher (Z.AI est a
sec) et attend 27 a 107 s par requete. Context7 repond en 0,5 s, gratuitement,
et ne peut pas servir une page de blocage -- le mode d'echec le plus cher
qu'on ait rencontre. Reste a savoir s'il rend quelque chose d'UTILE sur des
messages d'erreur, ce que sa vocation (documentation de bibliotheques) ne
garantit pas du tout.

LE CRITERE EST DECLARE AVANT LA MESURE, et il est ETROIT a dessein : le terme
qui NOMME LE CORRECTIF, pas celui qui nomme le sujet. "Dual" apparait dans
toute la doc de ForwardDiff et ne discrimine rien ; "tag" nomme la reparation
de la confusion de perturbation. Un critere large rendrait 6/6 et ne
mesurerait rien.

On ne publie PAS un taux : on publie la liste nominative. Six requetes, c'est
un tableau, pas une statistique.
"""
import io
import json
import os
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
API = "https://context7.com/api/v1"

# requete -> (termes qui NOMMENT le correctif, note sur la nettete du critere)
CRITERES = {
    "float64 gros-boutiste": (("bswap", "ntoh", "hton", "endian"), "net"),
    "derivee d'une constante": (("partials", "seed"), "FAIBLE : termes generiques"),
    "confusion de perturbation": (("tag", "nested"), "net : le tagging EST le correctif"),
    "has no field `partial`": (("partials",), "net : le champ est au pluriel"),
    "is ambiguous": (("ambigu",), "net"),
    "no method matching partial": (("partials",), "net : le champ est au pluriel"),
}


def _get(url, delai=30):
    t0 = time.time()
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "banc-julia/1.0"})
    with urllib.request.urlopen(req, timeout=delai) as r:
        return r.read().decode("utf-8", "replace"), time.time() - t0


def critere_de(requete):
    for cle, (termes, note) in CRITERES.items():
        if cle in requete:
            return termes, note
    return (), "AUCUN CRITERE DECLARE -- resultat non jugeable"


def rejouer(requete):
    out = {"requete": requete}
    try:
        brut, dt = _get("%s/search?query=%s" % (API, urllib.parse.quote(requete[:300])))
        out["ms_recherche"] = round(dt * 1000)
        res = json.loads(brut).get("results") or []
    except Exception as e:
        out["erreur"] = "recherche: %s" % e
        return out
    out["bibliotheques"] = [x.get("id") for x in res[:3]]
    if not res:
        out["erreur"] = "aucune bibliotheque resolue"
        return out
    lib = res[0].get("id", "").lstrip("/")
    out["retenue"] = lib
    try:
        doc, dt = _get("%s/%s?type=txt&topic=%s&tokens=2000"
                       % (API, lib, urllib.parse.quote(requete[:200])))
        out["ms_doc"] = round(dt * 1000)
    except Exception as e:
        out["erreur"] = "doc: %s" % e
        return out
    out["octets"] = len(doc)
    termes, note = critere_de(requete)
    bas = doc.lower()
    out["note_critere"] = note
    out["termes_attendus"] = list(termes)
    out["termes_trouves"] = [t for t in termes if t in bas]
    out["extrait"] = doc[:200].replace(chr(10), " ")
    return out


if __name__ == "__main__":
    src = os.path.join(BASE, "_requetes_reelles.json")
    if not os.path.exists(src):
        raise SystemExit("%s absent : extraire d abord les requetes reelles." % src)
    lignes = json.loads(io.open(src, encoding="utf-8").read())
    print("=== rejeu Context7 sur %d requetes REELLEMENT parties ===" % len(lignes))
    print("critere declare AVANT la mesure : le terme qui NOMME le correctif.")
    print()
    sorties = []
    for i, x in enumerate(lignes, 1):
        r = rejouer(x["requete"])
        r["tache"] = x["tache"]
        r["tour_suivant_reel"] = x["tour_suivant"]
        r["retenus_ancien_moteur"] = x["retenus"]
        sorties.append(r)
        print("%d. [%s tour+1 = %s]  %s" % (i, x["tache"], x["tour_suivant"],
                                            x["requete"][:78]))
        if r.get("erreur"):
            print("   ECHEC : %s" % r["erreur"])
        else:
            print("   -> %s   (%s ms + %s ms, %s octets)"
                  % (r["retenue"], r.get("ms_recherche"), r.get("ms_doc"),
                     r.get("octets")))
            print("   critere %s : attendu %s, trouve %s"
                  % (r["note_critere"], r["termes_attendus"], r["termes_trouves"] or "RIEN"))
        print()
    io.open(os.path.join(BASE, "_rejeu_context7.json"), "w", encoding="utf-8",
            newline=chr(10)).write(json.dumps(sorties, ensure_ascii=False, indent=1))
    print("liste nominative ci-dessus ; aucun taux publie (n=%d)." % len(lignes))
