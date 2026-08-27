"""SEMER LE CONTRAT D'API DANS LES STUBS cpp -- sans semer la solution.

POURQUOI. Les 26 exercices cpp du corpus livrent un stub VIDE (`namespace X {}`)
alors que le nom attendu n'est ecrit que dans le test officiel. En variante D ce
test est masque : l'agent doit DEVINER l'identifiant. Mesure du 27/08 :
cpp/gigasecond ecrit `anniversary`, le test appelle `advance`, la logique etait
juste. Ce n'est pas de la programmation qu'on mesure, c'est de la divination.

CE QU'ON SEME. Les DECLARATIONS de `.meta/example.h`, corps de fonction retires.
CE QU'ON NE SEME PAS. Aucun corps : 6 des 26 en-tetes en contiennent (inline),
ils seraient la solution.

METHODE. Parcours accolade par accolade. Une `{` qui ouvre un CORPS DE FONCTION
est reconnue a ce qui la precede : une `)` eventuellement suivie de
const/noexcept/override/= default/= delete, ou une liste d'initialisation de
constructeur `) : x_(a)`. Ces blocs-la sont remplaces par `;`. Les `{` de
namespace, class, struct, enum et union sont CONSERVEES : c'est la structure.
"""
import os, re, sys, shutil

CORPUS = os.path.join(os.environ["USERPROFILE"], "tools", "aider-bench", "aider",
                      "tmp.benchmarks", "polyglot-benchmark", "cpp",
                      "exercises", "practice")

# ce qui peut s'intercaler entre la `)` et la `{` d'un corps de fonction
QUEUE = re.compile(r"^[\s]*(const|noexcept|override|final|mutable|"
                   r"->[\w:<>,&*\s]+|:\s*[^{;]+)*[\s]*$")


def sans_corps(src):
    """retire les corps de fonction, garde toute autre accolade"""
    out = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c == '"' or c == "'":                 # chaine : recopier telle quelle
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            out.append(src[i:j + 1]); i = j + 1; continue
        if src.startswith("//", i):              # commentaire ligne
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(src[i:j]); i = j; continue
        if src.startswith("/*", i):              # commentaire bloc
            j = src.find("*/", i)
            j = n if j < 0 else j + 2
            out.append(src[i:j]); i = j; continue
        if c == "{":
            # ce bloc est-il un CORPS DE FONCTION ?
            avant = "".join(out)
            k = len(avant) - 1
            while k >= 0 and avant[k] in " \t\r\n":
                k -= 1
            # Trouver la `)` qui ferme la LISTE DE PARAMETRES. `rfind(")")` ne
            # suffit pas : dans `f(a) : _x(b), _y(c) {`, la derniere `)` est
            # celle de `_y(c)`. On balaie donc en arriere a profondeur de
            # parentheses, et on s'arrete au premier `:` de profondeur 0 qui
            # n'est pas `::` -- c'est le debut de la liste d'initialisation.
            # On remonte de `k` vers le debut. Une `)` ouvre une profondeur, une
            # `(` la ferme : les groupes parentheses sont donc SAUTES, et un `:`
            # rencontre a profondeur 0 est bien le debut d'une liste
            # d'initialisation (`) : _x(a), _y(b) {`). On coupe la signature
            # juste avant lui, puis on recommence -- il peut y en avoir plus
            # d'une couche. Ce qui reste se termine par la `)` des parametres.
            # Une seule regle, ancree sur la fin de `avant` : la `)` des
            # parametres, puis facultativement des qualificatifs, puis
            # facultativement une liste d'initialisation `: _x(a), _y(b)`.
            # `[^;{}]*` empeche de traverser une autre instruction ou un autre
            # bloc, donc la capture ne peut pas deborder sur du code voisin.
            mm = re.search(r"\)[\s\w]*(?::[^;{}]*)?\s*$", avant)
            ferme = mm.start() if mm else -1
            corps = False
            if ferme >= 0 and QUEUE.match(avant[ferme + 1:k + 1]):
                # rien entre la `)` et la `{` qui trahisse un class/enum
                seg = avant[ferme + 1:k + 1]
                if not re.search(r"\b(class|struct|enum|union|namespace)\b", seg):
                    corps = True
            if corps:
                prof = 0                          # sauter jusqu'a la `}` appariee
                j = i
                while j < n:
                    if src[j] == "{":
                        prof += 1
                    elif src[j] == "}":
                        prof -= 1
                        if prof == 0:
                            break
                    j += 1
                # La liste d'initialisation d'un constructeur (`) : _x(a), _y(b)`)
                # doit partir AVEC le corps : la garder produit un C++ invalide
                # (liste sans corps) ET fuite l'implementation. On ne conserve
                # que les qualificatifs qui font partie de la SIGNATURE.
                seg = avant[ferme + 1:k + 1]
                garde = re.sub(r"(?<!:):(?!:).*$", "", seg, flags=re.S).rstrip()
                # `out` melange caracteres et tranches : on le reconstruit en
                # une seule chaine plutot que d'y indexer.
                out = [avant[:ferme + 1] + garde + ";"]
                i = j + 1
                continue
        out.append(c)
        i += 1
    txt = "".join(out)
    txt = re.sub(r";\s*;+", ";", txt)      # `const ;;` -> `const;`
    txt = re.sub(r"\s+;", ";", txt)        # `data() const ;` -> `data() const;`
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    txt = re.sub(r"[ \t]+\n", "\n", txt)
    return txt


def main():
    applique = "--appliquer" in sys.argv
    if "--montrer" in sys.argv:
        for ex in sys.argv[sys.argv.index("--montrer") + 1:]:
            p = os.path.join(CORPUS, ex, ".meta", "example.h")
            print("=" * 22, ex, "=" * 22)
            print(sans_corps(open(p, encoding="utf-8", errors="ignore").read()).strip())
            print()
        return
    cibles = []
    for ex in sorted(os.listdir(CORPUS)):
        d = os.path.join(CORPUS, ex)
        meta = os.path.join(d, ".meta", "example.h")
        stub = os.path.join(d, ex.replace("-", "_") + ".h")
        if not os.path.isfile(stub):
            cand = [f for f in os.listdir(d) if f.endswith(".h")]
            if len(cand) != 1:
                print("  ?? %-28s stub introuvable (%s)" % (ex, cand)); continue
            stub = os.path.join(d, cand[0])
        if not os.path.isfile(meta):
            print("  ?? %-28s pas de .meta/example.h" % ex); continue
        cibles.append((ex, meta, stub))

    print("%d exercices cpp traites\n" % len(cibles))
    for ex, meta, stub in cibles:
        src = open(meta, encoding="utf-8", errors="ignore").read()
        gen = sans_corps(src)
        reste = len(re.findall(r"\)\s*(?:const\s*)?\{", gen))
        avant = len(open(stub, encoding="utf-8", errors="ignore").read().strip())
        etat = "OK " if reste == 0 else "!! %d corps restants" % reste
        print("  %-28s stub %4d car. -> %4d car.   %s" % (ex, avant, len(gen.strip()), etat))
        if applique:
            sauve = stub + ".stub-origine"
            if not os.path.exists(sauve):
                shutil.copy2(stub, sauve)
            open(stub, "w", encoding="utf-8", newline="\n").write(gen)
    if not applique:
        print("\n(essai a blanc -- relancer avec --appliquer pour ecrire)")


main()
