#!/bin/bash
# Etage 2 du banc qualite KV : ARC-challenge + PPL wikitext-2, 4 configs.
# Meme binaire (build-faq, FA_ALL_QUANTS) pour TOUTES les configs : le
# delta mesure la config KV, jamais la chaine. -fa on force flash-attn
# (le quantifie V l'exige ; auto pourrait choisir off et fausser un bras).
set -u
PPX=/c/Users/test/tools/llama-cpp/src-dflash2/build-faq/bin/Release/llama-perplexity.exe
MODEL=/c/Users/test/models/qwen38-27b/Qwen3.8-27B-Q4_K_M.gguf
ARC=/c/Users/test/models/datasets/arc-challenge-validation.bin
WIKI=/c/Users/test/models/datasets/wikitext-2-raw/wiki.test.raw
OUT=/c/Users/test/Documents/dsh2.0/reports/specdec_20260825_ctxsweep_dflash2

run_config () {
  local nom="$1"; shift
  echo "=== ARC $nom ==="
  "$PPX" -m "$MODEL" -bf "$ARC" --multiple-choice -ngl 99 -fa on "$@" \
    > "$OUT/stage2_arc_${nom}.txt" 2>&1
  tail -4 "$OUT/stage2_arc_${nom}.txt"
  echo "=== PPL $nom ==="
  "$PPX" -m "$MODEL" -f "$WIKI" -ngl 99 -fa on "$@" \
    > "$OUT/stage2_ppl_${nom}.txt" 2>&1
  tail -3 "$OUT/stage2_ppl_${nom}.txt"
}

run_config f16
run_config q8q8 -ctk q8_0 -ctv q8_0
run_config q8q4 -ctk q8_0 -ctv q4_0
run_config q4q4 -ctk q4_0 -ctv q4_0
echo "=== ETAGE 2 TERMINE ==="
