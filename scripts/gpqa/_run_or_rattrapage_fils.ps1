Set-Location "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
python gpqa_diamond.py or_bf16.jsonl `
    --url "https://openrouter.ai/api/v1" `
    --modele "qwen/qwen3.8-27b" `
    --dotenv "C:\Users\test\Documents\dsh2.0\.env" `
    --cle-env OPENROUTER_API_KEY `
    --questions 40 --rotations 4 --parallele 6 `
    --max-tokens 32768 --delai 900 `
    --extra-fichier extra_or_bf16.json
Write-Output "=== exit : $LASTEXITCODE ==="
