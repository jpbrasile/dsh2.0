"""Bascule `agent-default-model` dans ~/.dsh/settings.yaml : provider / model / effort.

Deux precautions, chacune payee par un defaut mesure :

1. ANCRAGE EN TEXTE, pas parse-and-dump. Charger le YAML et le re-serialiser
   reecrit TOUT le document (ordre des cles, guillemets, commentaires perdus) :
   mesure du 21/08, 390 lignes de diff pour en changer 3. On remplace ici les
   trois lignes concernees, et le reste du fichier est intouche a l'octet pres.

2. ECRITURE ATOMIQUE. `open(p, "w")` tronque le fichier AVANT que l'ecriture
   puisse echouer : une interruption a cet instant laisse la configuration dsh
   de l'utilisateur vide. On serialise a cote, puis on deplace.

PIEGE YAML 1.1 -- `off` non quote est le BOOLEEN false. La ligne ecrite pour le
niveau "off" est donc relue comme `reasoningEffort: False`. C'est la forme
exacte qui a servi a la campagne du 22/08, et la trace du proxy a montre que
dsh en fait bien `enable_thinking: false` sans cle d'effort. On la conserve
telle quelle pour rester reproductible ; `--montrer` imprime la valeur relue
pour que ce False soit visible et non pas subi.
"""
import io
import os
import re
import sys

CHEMIN = os.path.join(os.path.expanduser("~"), ".dsh", "settings.yaml")


def set_default(provider, model, effort, chemin=CHEMIN):
    """Reecrit les 3 lignes de agent-default-model. Rend le bloc obtenu."""
    s = io.open(chemin, encoding="utf-8").read()
    bloc = re.search(r"(?m)^agent-default-model:\n(?:[ \t]+.*\n)*", s)
    if not bloc:
        raise AssertionError(
            "bloc `agent-default-model:` introuvable dans %s -- refus d'ecrire "
            "a l'aveugle plutot que d'ajouter un second bloc qui masquerait "
            "silencieusement le premier." % chemin)
    ancien = bloc.group(0)
    lignes = []
    for l in ancien.split("\n"):
        if re.match(r"^\s+provider:", l):
            lignes.append("  provider: %s" % provider)
        elif re.match(r"^\s+model:", l):
            lignes.append("  model: %s" % model)
        elif re.match(r"^\s+reasoningEffort:", l):
            lignes.append("  reasoningEffort: %s" % effort)
        else:
            lignes.append(l)
    nouveau = "\n".join(lignes)
    if "reasoningEffort:" not in nouveau:
        nouveau = nouveau.rstrip("\n") + "\n  reasoningEffort: %s\n" % effort

    tmp = chemin + ".tmp-bench"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(s.replace(ancien, nouveau, 1))
    os.replace(tmp, chemin)
    return nouveau


def relire(chemin=CHEMIN):
    """Rend le bloc tel que le parseur YAML le voit -- pas tel qu'on l'a ecrit."""
    import yaml
    return yaml.safe_load(io.open(chemin, encoding="utf-8").read())["agent-default-model"]


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--montrer":
        print("agent-default-model (relu) ->", relire())
        raise SystemExit(0)
    if len(sys.argv) != 4:
        print(__doc__)
        print("usage: dsh_effort.py <provider> <model> <effort>")
        print("       dsh_effort.py --montrer")
        raise SystemExit(2)
    set_default(sys.argv[1], sys.argv[2], sys.argv[3])
    print("agent-default-model (relu) ->", relire())
