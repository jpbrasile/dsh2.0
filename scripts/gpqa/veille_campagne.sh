#!/bin/bash
# VEILLE DE CAMPAGNE. Une ligne toutes les 15 min, et une ligne immediate sur
# tout evenement qui demande une decision.
#
# Ce que la veille DOIT attraper -- le silence n'est pas une reussite :
#   - le bras GPQA qui se fige (compteur immobile depuis un tour de veille) ;
#   - la troncature qui remonte (c'est la raison d'etre du bras 8192) ;
#   - chaque exercice termine cote dsh puis cote pi, avec son verdict ;
#   - un exercice coupe au mur des 1800 s -- NON-MESURE, pas un echec, deja
#     arrive sur go/beer-song.
#
# PIEGE CORRIGE : `grep -c` IMPRIME deja 0 quand il ne trouve rien, et sort en
# code 1. Un `|| echo 0` ajoutait donc un SECOND 0, et le "0" suivi d'un "0"
# cassait l'arithmetique ("syntax error in expression"). `; true` neutralise le
# code de retour sans toucher a la sortie.
#
# La lecture d'un resultat d'agent est deportee dans lire_resultat_agent.py :
# du python cite dans du shell cite ne survit pas au canal.

G="C:/Users/test/Documents/dsh2.0/scripts/gpqa/local_q4_t1_budget8192.jsonl"
B="C:/Users/test/tools/aider-bench/aider/tmp.benchmarks/fumee-durs-dsh"
P="C:/Users/test/tools/aider-bench/aider/tmp.benchmarks/fumee-durs-pi"
LIRE="C:/Users/test/Documents/dsh2.0/scripts/gpqa/lire_resultat_agent.py"

prec_gpqa=-1
prec_res=""

while true; do
    n=$(wc -l < "$G" 2>/dev/null; true)
    tr=$(grep -c '"finish_reason": "length"' "$G" 2>/dev/null; true)
    ok=$(grep -c '"juste": true' "$G" 2>/dev/null; true)
    n=${n:-0}; tr=${tr:-0}; ok=${ok:-0}
    pct=0; ptr=0
    if [ "$n" -gt 0 ]; then
        pct=$(( ok * 100 / n ))
        ptr=$(( tr * 100 / n ))
    fi

    if [ "$n" -eq "$prec_gpqa" ] && [ "$prec_gpqa" -ge 0 ]; then
        echo "ALERTE GPQA : compteur fige a $n appels depuis 15 min."
    fi
    prec_gpqa=$n

    res=$( { find "$B" "$P" -name ".dsh.results.json" -o -name ".pi.results.json"; } 2>/dev/null | sort | tr '\n' ' ')
    if [ "$res" != "$prec_res" ] && [ -n "$prec_res" ]; then
        for f in $res; do
            case " $prec_res " in *" $f "*) continue;; esac
            python "$LIRE" "$f" 2>/dev/null
        done
    fi
    prec_res="$res"

    echo "veille  GPQA $n/792 appels, $pct % justes, $ptr % tronques  |  resultats agents : $(echo $res | wc -w)"
    sleep 900
done
