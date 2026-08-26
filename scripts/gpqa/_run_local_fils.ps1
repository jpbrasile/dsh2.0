Set-Location "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
python gpqa_diamond.py local_q4.jsonl --rotations 4 --max-tokens 16384 --parallele 1 --extra-fichier extra_local.json
Write-Output "=== exit : $LASTEXITCODE ==="
