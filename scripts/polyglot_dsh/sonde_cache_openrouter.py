# SONDE : qwen3.8-27b sur OpenRouter cache-t-il tout seul, ou faut-il poser
# un point de cache explicite ?
#
# LA CONTRADICTION QU'ELLE TRANCHE. Mesure du 26/08 : dsh obtient 24,7 % de
# jetons en cache et pi 78,3 %, PAR LE MEME PROXY, avec le meme modele et le
# meme fournisseur. Or la documentation OpenRouter range Alibaba/Qwen dans les
# fournisseurs a cache EXPLICITE (« add cache_control: {"type":"ephemeral"} to
# content blocks you want to cache »), le cache automatique ne couvrant
# qu'OpenAI, Grok, Moonshot, Groq, DeepSeek, Z.AI et Gemini. Les deux ne
# peuvent pas etre vrais tels quels : si le cache exigeait un marqueur, pi ne
# l'obtiendrait pas non plus. Et `cache_control` n'apparait nulle part dans le
# depot -- recherche faite, vide.
#
# TROIS CONDITIONS, meme prefixe, meme modele :
#   A  prefixe repete, SANS marqueur          -> le cache est-il automatique ?
#   B  prefixe repete, cache_control sur le bloc de contenu (forme Anthropic)
#   C  prefixe repete, cache_control au PREMIER NIVEAU de la requete
# C est teste parce que c'est la seule forme que le proxy sait deja injecter
# (PROXY_INJECT fusionne des champs de premier niveau) : si elle marche, la
# correction est une variable d'environnement et ne touche ni dsh ni pi.
#
# HORS PROXY, VOLONTAIREMENT. Passer par le 8009 ajouterait des lignes au
# journal de fil pendant que le run pi tourne et fausserait sa fenetre de
# mesure. La sonde appelle OpenRouter directement.
#
# LA CLE VIENT DE L'ENVIRONNEMENT et n'est ni affichee ni ecrite.

import io
import json
import os
import sys
import time
import urllib.request

CLE = os.environ.get("OPENROUTER_API_KEY")
if not CLE:
    raise SystemExit("OPENROUTER_API_KEY absente de l'environnement.")

MODELE = os.environ.get("SONDE_MODELE", "qwen/qwen3.8-27b")
URL = "https://openrouter.ai/api/v1/chat/completions"

# Prefixe long et STABLE. Le cache ne se declenche qu'au-dela d'un plancher de
# jetons ; on vise large pour ne pas confondre « pas de cache » et « trop court ».
BLOC = ("Reference table row %d: the identifier is REF-%05d, the category is "
        "category-%d, the status is nominal, and the recorded value is %d.\n")
PREFIXE = "".join(BLOC % (i, i * 7 + 3, i % 11, i * 13 % 997)
                  for i in range(1, 900))


def appel(marqueur, question):
    """marqueur : None | 'bloc' | 'racine'."""
    if marqueur == "bloc":
        contenu = [{"type": "text", "text": PREFIXE,
                    "cache_control": {"type": "ephemeral"}},
                   {"type": "text", "text": question}]
    else:
        contenu = PREFIXE + "\n" + question
    corps = {"model": MODELE, "max_tokens": 24,
             "messages": [{"role": "user", "content": contenu}]}
    if marqueur == "racine":
        corps["cache_control"] = {"type": "ephemeral"}
    req = urllib.request.Request(
        URL, data=json.dumps(corps).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + CLE})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    ms = (time.time() - t0) * 1000.0
    u = d.get("usage") or {}
    det = u.get("prompt_tokens_details") or {}
    return {
        "ms": ms,
        "entree": u.get("prompt_tokens") or 0,
        "cache": det.get("cached_tokens") or 0,
        "ecriture": det.get("cache_write_tokens") or 0,
        "fournisseur": d.get("provider") or "?",
        "erreur": (d.get("error") or {}).get("message") if d.get("error") else None,
    }


CAS = [(None, "A  sans marqueur           "),
       ("bloc", "B  cache_control sur bloc  "),
       ("racine", "C  cache_control racine    ")]

print("modele : %s   prefixe : ~%d caracteres" % (MODELE, len(PREFIXE)))
print("chaque cas = 2 appels : le 1er ECRIT le cache, le 2nd doit le LIRE.")
print()
print("%-28s %6s %9s %9s %10s %8s  %s"
      % ("cas", "appel", "entree", "en cache", "ecriture", "ms", "fournisseur"))

resume = {}
for marqueur, etiquette in CAS:
    lignes = []
    for n, q in ((1, "Give the status of row 42 in one word."),
                 (2, "Give the status of row 77 in one word.")):
        try:
            r = appel(marqueur, q)
        except Exception as e:
            print("%-28s %6d   ECHEC : %s" % (etiquette, n, str(e)[:80]))
            lignes = None
            break
        print("%-28s %6d %9d %9d %10d %8.0f  %s"
              % (etiquette, n, r["entree"], r["cache"], r["ecriture"],
                 r["ms"], r["fournisseur"]))
        lignes.append(r)
        time.sleep(3)  # le cache se construit en quelques secondes
    if lignes:
        resume[etiquette.strip()] = lignes[1]
    print()

print("=" * 70)
print("LECTURE")
for nom, r in resume.items():
    frac = 100.0 * r["cache"] / max(1, r["entree"])
    print("  %-28s 2e appel : %5.1f %% d'entree servie par le cache"
          % (nom, frac))
fournisseurs = {r["fournisseur"] for r in resume.values()}
if len(fournisseurs) > 1:
    print("  ATTENTION : les cas n'ont PAS ete servis par le meme fournisseur")
    print("  (%s) -- la comparaison entre cas est confondue par le routage."
          % ", ".join(sorted(fournisseurs)))
else:
    print("  Meme fournisseur pour tous les cas (%s) : la comparaison tient."
          % list(fournisseurs)[0] if fournisseurs else "  Aucun cas abouti.")
print()
print("Si A est deja eleve, le cache est AUTOMATIQUE et l'ecart dsh/pi vient")
print("de la STABILITE DU PREFIXE, pas d'un marqueur manquant. Si seul B ou C")
print("est eleve, il manque un point de cache -- et C, injectable par le proxy")
print("via PROXY_INJECT, corrigerait les deux agents sans les modifier.")
