Set-Location "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
python gpqa_diamond.py local_q4_t1_b8192_tournant.jsonl `
    --rotation-tournante --max-tokens 16384 --parallele 1 `
    --temperature 1.0 --top-p 0.95 `
    --extra-fichier extra_local.json
Write-Output "=== exit : $LASTEXITCODE ==="
