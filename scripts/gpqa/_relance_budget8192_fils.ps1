# ENVELOPPE. Appelee SANS argument par Start-Process, elle appelle le lanceur
# avec le message comme VARIABLE PowerShell.
#
# POURQUOI CETTE ENVELOPPE EXISTE. Premier essai : le message etait passe dans
# le -ArgumentList de Start-Process. PowerShell y rejoint le tableau par des
# espaces puis re-decoupe : le message s'est fragmente et le mot « is » a fini
# lie au parametre -Port ("Impossible de convertir la valeur is en Int32").
# Un texte destine a etre LU ne passe pas par un argument shell. Ici il ne
# traverse aucun re-decoupage : `& $script -ReasoningBudgetMessage $msg` lie une
# seule valeur.
#
# Message sur UNE ligne : un saut de ligne dans un argument survit a PowerShell
# mais pas forcement a la ligne de commande native que CreateProcess reconstruit.
# Guillemets SIMPLES : $LETTER doit arriver LITTERAL au modele.

$msg = 'My thinking budget is now exhausted. I will stop analysing, commit to the single most likely option, and finish my response with the required last line: Answer: $LETTER'

& "C:\Users\test\Documents\dsh2.0\scripts\start_llama_qwen38_27b_specdec.ps1" `
    -Config q38-dflash2 `
    -BinaryPath "C:\Users\test\tools\llama-cpp\src-dflash2\build-faq\bin\Release\llama-server.exe" `
    -CtxSize 163840 `
    -Ctk q8_0 -Ctv q4_0 `
    -SpecDraftNMax 7 `
    -AssumeDflash2Capable `
    -ReasoningBudget 8192 `
    -ReasoningBudgetMessage $msg
