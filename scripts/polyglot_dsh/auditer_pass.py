"""AUDITER LES PASS -- un succes se verifie aussi durement qu'un echec.

POURQUOI. Jusqu'ici chaque FAIL a ete ouvert et diagnostique, et les PASS ont
ete comptes sans etre regardes. C'est asymetrique, et c'est le mauvais sens :
un FAIL indument compte coute des points, un PASS indument compte DETRUIT le
chiffre. En variante D les facons d'obtenir un faux PASS sont concretes :

  * le juge a note le test de l'AGENT au lieu du test officiel (le fichier
    officiel a ete edite, ou l'agent a ecrit a son nom) ;
  * la suite officielle n'a pas ete RECOMPILEE et le juge a lu un artefact du
    tour precedent ;
  * en cpp depuis le 27/08, CMakeLists.txt est editable : un recablage vers le
    test maison ferait passer l'exercice sans que la vraie suite tourne. La
    restauration avant le juge existe -- ce script VERIFIE qu'elle a eu lieu ;
  * l'agent n'a rien ecrit et le stub passait deja (exercice trivial ou suite
    vide).

CE QUE LE SCRIPT CONTROLE, sans conteneur et sans rien relancer :

  1. FICHIERS DE TEST identiques a l'original, octet pour octet ;
  2. FICHIERS DE CONSTRUCTION identiques a l'original (cf. CONSTRUCTION) ;
  3. la SOLUTION differe du stub -- l'agent a bien ecrit quelque chose ;
  4. aucun test ECRIT PAR L'AGENT ne subsiste la ou le juge le ramasserait.

Un PASS qui echoue a l'un de ces quatre points est signale SUSPECT et doit etre
rejoue a la main avant publication. Le script ne corrige rien et ne note rien :
il dit ce qu'il voit.

Usage :  python auditer_pass.py <nom_du_run>            (ex. pi_dimD2)
         python auditer_pass.py <nom_du_run> --tous      (audite aussi les FAIL)
"""
import os, sys, json, hashlib, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilote

BENCH = os.path.join(os.environ["USERPROFILE"], "tools", "aider-bench", "aider",
                     "tmp.benchmarks")
VIERGE = os.path.join(BENCH, "polyglot-benchmark")


def sceau(chemin):
    if not os.path.isfile(chemin):
        return None
    h = hashlib.sha256()
    h.update(open(chemin, "rb").read())
    return h.hexdigest()


def auditer(ex_hote, ex_vierge, res):
    """Rend la liste des anomalies. Vide = le PASS tient."""
    anomalies = []
    cfg_p = os.path.join(ex_vierge, ".meta", "config.json")
    cfg = json.load(open(cfg_p, encoding="utf-8")) if os.path.isfile(cfg_p) else {}
    tests = cfg.get("files", {}).get("test", [])
    solution = cfg.get("files", {}).get("solution", [])

    # 1. les tests officiels sont-ils ceux de l'original ?
    for f in tests:
        a = sceau(os.path.join(ex_hote, f.replace("/", os.sep)))
        b = sceau(os.path.join(ex_vierge, f.replace("/", os.sep)))
        if b is None:
            anomalies.append("test absent de l'original : %s" % f)
        elif a is None:
            anomalies.append("TEST OFFICIEL MANQUANT au moment du verdict : %s" % f)
        elif a != b:
            anomalies.append("TEST OFFICIEL MODIFIE : %s" % f)

    # 2. la construction est-elle revenue a l'original ?
    for f in pilote.fichiers_construction(ex_vierge, cfg):
        a = sceau(os.path.join(ex_hote, f.replace("/", os.sep)))
        b = sceau(os.path.join(ex_vierge, f.replace("/", os.sep)))
        if a != b:
            anomalies.append("CONSTRUCTION NON RESTAUREE : %s" % f)

    # 3. l'agent a-t-il ecrit quelque chose dans le fichier note ?
    bouge = False
    for f in solution:
        a = sceau(os.path.join(ex_hote, f.replace("/", os.sep)))
        b = sceau(os.path.join(ex_vierge, f.replace("/", os.sep)))
        if a is not None and a != b:
            bouge = True
    if not bouge and solution:
        anomalies.append("SOLUTION INCHANGEE : le stub d'origine a ete note tel quel")

    # 3bis. la solution est-elle le CORRIGE recopie ? En variante D `.meta` est
    #       masque (--sans-corriges), donc ce ne devrait pas etre possible --
    #       raison de plus pour le verifier plutot que de le supposer.
    exemples = cfg.get("files", {}).get("example", [])
    sceaux_ex = {sceau(os.path.join(ex_vierge, f.replace("/", os.sep)))
                 for f in exemples}
    sceaux_ex.discard(None)
    for f in solution:
        chemin = os.path.join(ex_hote, f.replace("/", os.sep))
        a = sceau(chemin)
        if a is None or a not in sceaux_ex:
            continue
        # CAS ATTENDU, et pas une fraude : l'en-tete cpp SEME le 27/08 porte les
        # declarations de `.meta/example.h`, corps retires. Quand cet en-tete de
        # reference ne contenait AUCUN corps -- le cas de gigasecond -- le semis
        # est forcement identique a la reference. Ce n'est pas la solution : la
        # solution cpp est dans example.cpp, jamais dans le .h.
        # La signature du semis, c'est la sauvegarde `<ex>.h.stub-origine`
        # laissee a cote du stub dans le corpus d'origine.
        seme = os.path.isfile(os.path.join(
            ex_vierge, f.replace("/", os.sep) + ".stub-origine"))
        corps = re.search(r"\)\s*(?:const\s*)?\{", open(
            chemin, encoding="utf-8", errors="ignore").read())
        if seme and not corps:
            anomalies.append("(info) %s est l'en-tete de reference SANS aucun"
                             " corps : c'est le semis du 27/08, pas une fuite" % f)
        else:
            anomalies.append("SOLUTION = LE CORRIGE .meta recopie : %s" % f)

    # 4. tout test ecrit par l'agent a-t-il bien ete SORTI pendant le verdict ?
    #
    #    ATTENTION AU MOMENT QU'ON REGARDE -- premiere version de ce controle
    #    fausse, le 27/08 : elle signalait la simple PRESENCE d'un test maison
    #    dans le repertoire, et rendait 5 suspects sur 5. Or le pilote SORT ces
    #    fichiers le temps du verdict puis les REMET (`finally: demasquer`) :
    #    apres le run ils sont forcement la. Leur presence ne prouve rien.
    #
    #    Ce qui se verifie vraiment : tout fichier ressemblant a un test, absent
    #    du corpus d'origine, doit figurer dans `tests_ecrits_par_l_agent` --
    #    c'est LA liste que le pilote a masquee. Un test que cette liste ignore
    #    est un test que le juge a pu ramasser.
    masques = {f.replace("\\", "/") for f in res.get("tests_ecrits_par_l_agent", [])}
    officiels = {f.replace("\\", "/") for f in tests}
    for cur, dirs, fics in os.walk(ex_hote):
        dirs[:] = [d for d in dirs if d not in
                   (".meta", ".docs", ".approaches", "build", "node_modules",
                    "target", ".git", ".gradle")]
        for f in fics:
            rel = os.path.relpath(os.path.join(cur, f), ex_hote).replace("\\", "/")
            if rel in officiels or rel in masques:
                continue
            # present dans le corpus d'origine = fichier du corpus, pas de
            # l'agent (ex. cpp `test/tests-main.cpp`, le main de Catch2).
            if os.path.isfile(os.path.join(ex_vierge, rel.replace("/", os.sep))):
                continue
            if any(re.search(m, rel) for m in pilote.MOTIFS_TEST):
                anomalies.append("test NON MASQUE au verdict : %s" % rel)
    return anomalies


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    run = sys.argv[1]
    tous = "--tous" in sys.argv
    racine = os.path.join(BENCH, run)
    if not os.path.isdir(racine):
        raise SystemExit("run introuvable : %s" % racine)

    lignes, suspects, vus = [], 0, 0
    for langue in sorted(os.listdir(racine)):
        base = os.path.join(racine, langue, "exercises", "practice")
        if not os.path.isdir(base):
            continue
        for ex in sorted(os.listdir(base)):
            d = os.path.join(base, ex)
            rp = os.path.join(d, ".dsh.results.json")
            if not os.path.isfile(rp):
                continue
            res = json.load(open(rp, encoding="utf-8"))
            ok = bool(res.get("tests_outcomes", [False])[-1])
            if not ok and not tous:
                continue
            vus += 1
            ev = os.path.join(VIERGE, langue, "exercises", "practice", ex)
            anomalies = auditer(d, ev, res)
            etat = "PASS" if ok else "fail"
            # Les lignes « (info) » decrivent un etat ATTENDU et verifie ; elles
            # s'affichent mais ne rendent rien suspect.
            graves = [a for a in anomalies if not a.startswith("(info)")]
            if anomalies:
                # Seul un PASS anormal met en cause le CHIFFRE : un FAIL signale
                # est une information (ex. « solution inchangee » = l'agent n'a
                # rien ecrit), pas une menace sur le taux.
                if ok and graves:
                    suspects += 1
                if ok and graves:
                    marque = "SUSPECT"
                elif graves:
                    marque = "note"
                else:
                    marque = "tient"
                lignes.append("  %-11s %-26s %s  %s" % (langue, ex, etat, marque))
                for a in anomalies:
                    lignes.append("        ! %s" % a)
            else:
                lignes.append("  %-11s %-26s %s  tient" % (langue, ex, etat))

    print("=== AUDIT DES %s -- run %s ===" % ("VERDICTS" if tous else "PASS", run))
    print("\n".join(lignes) if lignes else "  (aucun verdict a auditer)")
    print()
    print("%d audite(s), %d suspect(s)." % (vus, suspects))
    if suspects:
        print("Un PASS suspect doit etre rejoue a la main AVANT publication.")
        raise SystemExit(1)


main()
