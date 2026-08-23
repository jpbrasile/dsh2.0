# -*- coding: utf-8 -*-
"""Liste les appels d'outils d'un journal de session dsh (session.jsonl.zstd) : qui a appele
quoi, avec quels arguments (tronques), et ce que l'outil a rendu (tronque). Sert a lire une
fumee apres coup sans rejouer : le fil (wire.jsonl) ne porte que des metadonnees, le journal
porte le contenu -- c'est un fichier LOCAL de l'accueil isole _fumee/home, jamais du depot.

    python harness/session_outils.py <dossier sessions | fichier .zstd> [--large N]
"""
import argparse, io, json, os, sys

try:
    import zstandard
except ImportError:
    raise SystemExit("pip install zstandard")


def lire(p):
    with io.open(p, "rb") as f:
        data = zstandard.ZstdDecompressor().stream_reader(f).read()
    for l in data.decode("utf-8", "replace").splitlines():
        if l.strip():
            try:
                yield json.loads(l)
            except ValueError:
                continue


def court(x, n):
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
    s = s.replace("\n", "\\n")
    return s if len(s) <= n else s[:n] + "...(%d)" % len(s)


def parcourir(obj, chemin=""):
    """Rend (chemin, dict) pour tout dict imbrique."""
    if isinstance(obj, dict):
        yield chemin, obj
        for k, v in obj.items():
            yield from parcourir(v, chemin + "/" + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from parcourir(v, chemin + "[%d]" % i)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cible")
    ap.add_argument("--large", type=int, default=160)
    A = ap.parse_args()
    fichiers = []
    if os.path.isdir(A.cible):
        for root, _, fs in os.walk(A.cible):
            fichiers += [os.path.join(root, f) for f in fs if f.endswith(".zstd")]
    else:
        fichiers = [A.cible]
    fichiers.sort(key=os.path.getmtime)
    for p in fichiers:
        print("== %s (%d o)" % (p[-80:], os.path.getsize(p)))
        n = 0
        for e in lire(p):
            for ch, d in parcourir(e):
                # appel d'outil : {"type":"tool_call"|"toolCall", "name":..., "arguments"|"input":...}
                nom = d.get("name") or d.get("toolName") or d.get("tool")
                args = d.get("arguments") if "arguments" in d else d.get("input") if "input" in d else d.get("args")
                if nom and isinstance(args, (dict, str)) and ("tool" in str(d.get("type", "")).lower() or "tool" in ch.lower() or "call" in str(d.get("type", "")).lower()):
                    n += 1
                    print("  APPEL %-28s %s" % (nom, court(args, A.large)))
                # resultat d'outil
                if str(d.get("type", "")).lower() in ("tool_result", "toolresult", "tool-result") or ("tool_call_id" in d and "content" in d) or ("toolCallId" in d and ("content" in d or "output" in d or "result" in d)):
                    res = d.get("content") if "content" in d else d.get("output") if "output" in d else d.get("result")
                    print("  -> %s" % court(res, A.large))
        print("  (%d appel(s) d'outil detecte(s))" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
