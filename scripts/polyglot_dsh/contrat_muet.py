"""LA SEMANTIQUE EST-ELLE ECRITE AILLEURS QUE DANS LE TEST CACHE ?

Le semis de signatures (26 stubs cpp) a regle le NOM. Il ne regle pas le
COMPORTEMENT. Cas mesure le 27/08 : go/simple-linked-list. Le stub declare
`Push`, `Pop`, `Array`, `Reverse` -- tout est la. Mais l'enonce ne dit NULLE
PART que `Push` ajoute EN FIN (le test exige New([1,2,3]) + Push(4) ->
[1,2,3,4]). L'agent a empile en TETE, avec un `New` qui compense : il passe
New/Size/Array/Pop et echoue sur Push. Ce n'est pas une erreur de
programmation, c'est une convention non ecrite.

MESURE (proxy, et annonce comme tel). Pour chaque exercice : les identifiants
DECLARES par le stub editable sont-ils au moins CITES par l'enonce ? Si l'enonce
ne nomme aucun d'eux, la semantique de ces fonctions ne peut venir que du test
-- masque en variante D.

Ce proxy MINORE le defaut : citer `Push` ne dit pas ou il empile. Le chiffre
rendu est donc un PLANCHER, jamais un total.
"""
import os, re, collections

CORPUS = os.path.join(os.environ["USERPROFILE"], "tools", "aider-bench", "aider",
                      "tmp.benchmarks", "polyglot-benchmark")

DECL = {
    ".h":   re.compile(r"[\w:<>,&*\s]\b(\w+)\s*\([^)]*\)\s*(?:const\s*)?;"),
    ".go":  re.compile(r"^func\s+(?:\([^)]*\)\s*)?(\w+)", re.M),
    ".py":  re.compile(r"^\s*(?:def|class)\s+(\w+)", re.M),
    ".js":  re.compile(r"(?:export\s+(?:const|function|class)|^\s*(?:function|class))\s+(\w+)", re.M),
    ".rs":  re.compile(r"^\s*pub\s+(?:fn|struct|enum|trait)\s+(\w+)", re.M),
    ".java": re.compile(r"^\s*(?:public |private |protected |static |final |abstract )*"
                        r"[\w<>\[\],. ]+\s+(\w+)\s*\([^)]*\)", re.M),
}
EXT = {"cpp": (".h",), "go": (".go",), "python": (".py",),
       "javascript": (".js",), "rust": (".rs",), "java": (".java",)}

# noms trop generiques pour prouver quoi que ce soit s'ils apparaissent
BRUIT = {"main", "new", "String", "toString", "equals", "list", "class", "int",
         "get", "set", "value", "run", "test", "init", "self", "type"}


def enonce(d):
    """tout ce que l'agent peut lire : .docs/instructions*.md + introduction"""
    txt = []
    doc = os.path.join(d, ".docs")
    if os.path.isdir(doc):
        for f in sorted(os.listdir(doc)):
            if f.endswith(".md"):
                txt.append(open(os.path.join(doc, f), encoding="utf-8",
                                errors="ignore").read())
    return "\n".join(txt)


stats = collections.defaultdict(lambda: [0, 0])
muets = []

for langue, exts in EXT.items():
    base = os.path.join(CORPUS, langue, "exercises", "practice")
    if not os.path.isdir(base):
        continue
    for ex in sorted(os.listdir(base)):
        d = os.path.join(base, ex)
        if not os.path.isdir(d):
            continue
        noms = set()
        for racine, dirs, fics in os.walk(d):
            dirs[:] = [x for x in dirs if x not in
                       (".meta", ".docs", ".approaches", "build", "node_modules",
                        "target", ".git")]
            for f in fics:
                e = os.path.splitext(f)[1]
                if e not in exts or "test" in f.lower() or "spec" in f.lower():
                    continue
                if f.endswith(".stub-origine"):
                    continue
                src = open(os.path.join(racine, f), encoding="utf-8",
                           errors="ignore").read()
                for m in DECL[e].findall(src):
                    if m and m not in BRUIT and len(m) > 2:
                        noms.add(m)
        if not noms:
            continue
        stats[langue][1] += 1
        txt = enonce(d).lower()
        cites = [n for n in noms if n.lower() in txt]
        if not cites:
            stats[langue][0] += 1
            muets.append((langue, ex, sorted(noms)[:5]))

print("=== L'ENONCE NE CITE AUCUN IDENTIFIANT DECLARE PAR LE STUB ===")
print("(plancher : citer un nom ne dit toujours pas ce qu'il fait)\n")
print("%-12s %10s %8s %8s" % ("langue", "aucun cite", "total", "part"))
tm = tt = 0
for langue in ("cpp", "go", "java", "javascript", "python", "rust"):
    m, t = stats[langue]
    tm += m; tt += t
    if t:
        print("%-12s %10d %8d %7.0f %%" % (langue, m, t, 100.0 * m / t))
print("%-12s %10d %8d %7.0f %%" % ("TOTAL", tm, tt, 100.0 * tm / tt if tt else 0))
print()
print("=== 25 premiers ===")
for langue, ex, noms in muets[:25]:
    print("   %-11s %-28s declare : %s" % (langue, ex, ", ".join(noms)))
