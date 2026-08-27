"""COMBIEN D'EXERCICES CACHENT LEUR CONTRAT D'API ?

Constat sur cpp/gigasecond : le test officiel attend gigasecond::advance, le
stub livre un namespace VIDE, et TASK.md ne nomme aucune fonction. En variante
D le test est masque, donc le nom n'est ecrit NULLE PART que l'agent puisse
lire. Il doit le deviner.

Rust, lui, livre `pub fn after(start: DateTime) -> DateTime { todo!() }` : le
contrat est dans le stub, la variante D y est jouable.

On compte donc, sur les 225 exercices, ceux dont le stub editable ne contient
AUCUNE declaration. Ce sont les exercices ou la variante D mesure la
divination, pas la programmation.
"""
import os, re, json, collections

CORPUS = os.path.join(os.environ["USERPROFILE"], "tools", "aider-bench", "aider",
                      "tmp.benchmarks", "polyglot-benchmark")

# motif de declaration par extension
DECL = {
    ".h":   re.compile(r"\w[\w:<>,&*\s]*\s+\w+\s*\([^)]*\)\s*;"),
    ".cpp": re.compile(r"\w[\w:<>,&*\s]*\s+\w+\s*\([^)]*\)\s*\{"),
    ".go":  re.compile(r"^func\s+\w+", re.M),
    ".py":  re.compile(r"^\s*(def|class)\s+\w+", re.M),
    ".js":  re.compile(r"(export\s+(const|function|class)|^\s*(function|class)\s+\w+)", re.M),
    ".rs":  re.compile(r"^\s*pub\s+(fn|struct|enum|trait)\s+\w+", re.M),
    # Le stub java d'Exercism declare ses methodes SANS modificateur d'acces
    # (`void open() throws ... {`). Un motif exigeant public/private/static les
    # rate toutes et compte l'exercice comme muet a tort -- faute commise le
    # 27/08, corrigee ici. On accepte donc toute signature suivie d'une
    # accolade, plus les declarations de type.
    ".java": re.compile(
        r"^\s*[\w<>\[\],. ]+\s+\w+\s*\([^)]*\)\s*(throws [\w ,.]+)?\s*\{"
        r"|^\s*(public |abstract |final )*(class|interface|enum|record)\s+\w+",
        re.M),
}
EXT_LANG = {"cpp": (".h", ".cpp"), "go": (".go",), "python": (".py",),
            "javascript": (".js",), "rust": (".rs",), "java": (".java",)}

def est_test(nom):
    n = nom.lower()
    return "test" in n or "spec" in n

stats = collections.defaultdict(lambda: [0, 0])   # langue -> [muets, total]
muets = []

for langue, exts in EXT_LANG.items():
    base = os.path.join(CORPUS, langue, "exercises", "practice")
    if not os.path.isdir(base):
        continue
    for ex in sorted(os.listdir(base)):
        d = os.path.join(base, ex)
        if not os.path.isdir(d):
            continue
        # fichiers editables : hors .meta, .docs, hors tests
        cands = []
        for racine, dirs, fics in os.walk(d):
            dirs[:] = [x for x in dirs
                       if x not in (".meta", ".docs", ".approaches", "build",
                                    "node_modules", "target", ".git")]
            for f in fics:
                e = os.path.splitext(f)[1]
                if e in exts and not est_test(f):
                    cands.append(os.path.join(racine, f))
        if not cands:
            continue
        stats[langue][1] += 1
        a_decl = False
        for c in cands:
            try:
                txt = open(c, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            e = os.path.splitext(c)[1]
            if DECL[e].search(txt):
                a_decl = True
                break
        if not a_decl:
            stats[langue][0] += 1
            muets.append((langue, ex))

print("=== EXERCICES DONT LE STUB NE DECLARE RIEN ===")
print("%-12s %8s %8s %8s" % ("langue", "muets", "total", "part"))
tm = tt = 0
for langue in ("cpp", "go", "java", "javascript", "python", "rust"):
    m, t = stats[langue]
    tm += m; tt += t
    if t:
        print("%-12s %8d %8d %7.0f %%" % (langue, m, t, 100.0 * m / t))
print("%-12s %8d %8d %7.0f %%" % ("TOTAL", tm, tt, 100.0 * tm / tt if tt else 0))
print()
print("Ces %d exercices sont ceux ou la variante D, telle qu'elle tourne," % tm)
print("demande a l'agent d'inventer le nom exact attendu par un test qu'il ne")
print("voit pas. Le taux qu'ils produisent ne mesure pas la programmation.")
print()
print("=== les 20 premiers ===")
for langue, ex in muets[:20]:
    print("   %-12s %s" % (langue, ex))
