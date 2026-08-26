# Pose la sonde de prefixe dans proxy.mjs. IDEMPOTENT, et refuse de tourner si
# le proxy sert un banc en cours.
#
# CE QU'ELLE AJOUTE, ET POURQUOI CHAQUE CHAMP.
#
#   roles COMPLET      proxy.mjs journalisait `p.messages.slice(0, 3)`. Sur une
#                      conversation de 32 messages, comparer trois roles entre
#                      deux appels ne peut que rendre « extension » : les trois
#                      premiers messages ne changent pas de role. Mon test du
#                      26/08 mesurait cette tautologie.
#   msg_chars          longueur de contenu par message : montre LEQUEL enfle ou
#                      change, ce qu'une longueur totale noie.
#   prefix_h           empreinte CUMULEE apres chaque message. Deux appels
#                      successifs se comparent par recherche du premier indice
#                      qui diverge -- c'est l'endroit exact ou le prefixe casse,
#                      donc ou le cache meurt. C'est le seul champ qui reponde
#                      a la question posee.
#   fournisseur        ABSENT du journal : `servi` ne porte que le nom du
#                      modele. Sans lui, tout ecart dsh/pi reste confondu par le
#                      routage -- la sonde du 26/08 a montre que ce modele est
#                      servi par Phala et non par Alibaba, et que cette
#                      difference decide du comportement de cache.
#
# CE QU'ELLE NE FAIT PAS. Elle ne journalise AUCUN contenu : seulement des
# longueurs et des empreintes. Un prompt d'exercice ne doit pas se retrouver en
# clair dans un journal qu'on partage.
#
# Le proxy doit etre RELANCE apres pose : un processus node ne relit pas son
# fichier. Le banc GPQA ne passe pas par ce proxy (il tape le llama-server local
# sur 8005) : le relancer ne le derange pas.

import io
import os
import re
import subprocess
import sys

CHEMIN = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "..", "bench_julia_effort", "proxy.mjs")
CHEMIN = os.path.normpath(CHEMIN)
MARQUE = "prefix_h"

AIDE = """    // --- sonde de prefixe (26/08) : ou le cache meurt-il ? -------------
    // Empreinte FNV-1a 32 bits, cumulee message par message. On ne stocke
    // AUCUN contenu, seulement des longueurs et des empreintes.
    const _fnv = (s) => {
      let h = 0x811c9dc5;
      for (let i = 0; i < s.length; i++) {
        h ^= s.charCodeAt(i);
        h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
      }
      return h.toString(16).padStart(8, '0');
    };
    const _texte = (m) => {
      if (!m) return '';
      const c = m.content;
      if (typeof c === 'string') return c;
      if (Array.isArray(c)) return c.map((b) => (b && b.text) || '').join('');
      return '';
    };
"""

NOUVEAU_ROLES = """          roles: Array.isArray(p.messages) ? p.messages.slice(0, 300).map((m) => (m && m.role) || '?') : null,
          msg_chars: Array.isArray(p.messages) ? p.messages.slice(0, 300).map((m) => _texte(m).length) : null,
          // Empreinte du prefixe APRES chaque message : le premier indice ou
          // deux appels successifs divergent est l'endroit ou le cache meurt.
          // On seme avec le prompt systeme ET la liste d'outils, qui precedent
          // les messages dans le prompt reellement servi.
          prefix_h: Array.isArray(p.messages) ? (() => {
            let acc = _fnv(JSON.stringify(p.tools || []));
            const out = [acc];
            for (const m of p.messages.slice(0, 300)) {
              acc = _fnv(acc + '|' + ((m && m.role) || '?') + '|' + _texte(m));
              out.push(acc);
            }
            return out;
          })() : null,"""

ANCRES = [
    ("          roles: Array.isArray(p.messages) ? p.messages.slice(0, 3)"
     ".map((m) => (m && m.role) || '?') : null,", NOUVEAU_ROLES),
    ("            if (o && o.model) { rec.servi = o.model; break; }",
     "            if (o && o.provider && !rec.fournisseur) rec.fournisseur = o.provider;\n"
     "            if (o && o.model) { rec.servi = o.model; break; }"),
    ("          if (last.model) rec.servi = last.model;",
     "          if (last.provider) rec.fournisseur = last.provider;\n"
     "          if (last.model) rec.servi = last.model;"),
    ("        sent = {", AIDE + "        sent = {"),
]


def occupe():
    """Un banc utilise-t-il le proxy en ce moment ?"""
    try:
        s = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -match 'pilote.py' } | "
             "Measure-Object | Select-Object -ExpandProperty Count"],
            stderr=subprocess.STDOUT).decode("utf-8", "replace").strip()
        return int(re.sub(r"\D", "", s) or "0")
    except Exception as e:
        print("Impossible de verifier les bancs en cours : %s" % e)
        return -1


n = occupe()
if n != 0:
    print("REFUS : %s pilote(s) en cours. On ne modifie pas un instrument"
          % ("verification impossible, " if n < 0 else n))
    print("pendant la mesure. Relancer quand le banc pi est fini.")
    raise SystemExit(2)

texte = io.open(CHEMIN, encoding="utf-8").read()
if MARQUE in texte:
    print("Deja pose (%s present dans %s). Rien a faire." % (MARQUE, CHEMIN))
    raise SystemExit(0)

for ancre, remplacement in ANCRES:
    if texte.count(ancre) != 1:
        print("REFUS : ancre absente ou ambigue (%d occurrences) :"
              % texte.count(ancre))
        print("  %s" % ancre[:100])
        raise SystemExit(3)

sauve = CHEMIN + ".avant-sonde"
if not os.path.exists(sauve):
    io.open(sauve, "w", encoding="utf-8", newline="\n").write(texte)
    print("sauvegarde : %s" % sauve)

for ancre, remplacement in ANCRES:
    texte = texte.replace(ancre, remplacement, 1)
io.open(CHEMIN, "w", encoding="utf-8", newline="\n").write(texte)
print("sonde posee dans %s" % CHEMIN)

# Le fichier doit rester du JS valide : on le fait verifier par node lui-meme.
try:
    r = subprocess.run([os.environ.get("NODE", "node"), "--check", CHEMIN],
                       capture_output=True)
    if r.returncode != 0:
        io.open(CHEMIN, "w", encoding="utf-8", newline="\n").write(
            io.open(sauve, encoding="utf-8").read())
        print("SYNTAXE INVALIDE -- fichier RESTAURE depuis %s" % sauve)
        print(r.stderr.decode("utf-8", "replace")[:600])
        raise SystemExit(4)
    print("node --check : ok")
except FileNotFoundError:
    print("ATTENTION : node introuvable, syntaxe NON verifiee.")

print()
print("RELANCER LE PROXY : un node ne relit pas son fichier.")
print("Le banc GPQA ne passe pas par ce proxy (llama-server local, port 8005).")
