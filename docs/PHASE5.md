# Phase 5 — couche de coût : Qwen local (case 1)

Périmètre exécuté le 24/08/2026 (ordre utilisateur : « fais le qwen local en
automode, arrête avant les nightly automatiques » ; GPU signalé occupé —
politique appliquée : 3 mesures espacées de 60 s, seul résident CUDA admis =
le serveur julia_gate, propriétaire du port 8077). **freellmapi (case 2) non
commencé. Aucune automatisation posée : pas de cron, défaut du distilleur
inchangé (OpenRouter), serveur arrêté en fin de validation.**

## Ce qui existe désormais

| Pièce | Où | Preuve |
|---|---|---|
| Lanceur production | `scripts/start_llama_qwen_local.ps1` (:8004, alias `qwen-local`, Qwen3.8-27B Q4_K_M, ctx 32768, KV f16/f16, garde GPU gate-aware, `-Embeddings` opt-in, `-CheckOnly`) | CheckOnly PASS ; run vif ci-dessous |
| Route dsh | bloc `qwen-local` de `harness/providers.yaml`, installé (11 providers relus) | fumée verte ci-dessous |
| Amont local fumée | `fumee_route.py` : `--amont http(s)://hote[:port]` ; réécriture openrouter.ai restreinte au port 8050 ; **port d'enregistreur tenu = refus bruyant** | probation 2/3 vertes ci-dessous |
| Distillation locale | `distiller.py` : env `DISTILLER_URL` (opt-in), Bearer factice si URL locale | run J10 ci-dessous |
| Probation locale | `modeles.py --local-upsert` (provider `local`, tier PRIVATE+OPEN, prix 0, survit au `--rafraichir`, probation jusqu'à 3 verts minimal) | verdict VERT enregistré ; unités 46/46 |

## Mesures (24/08, RTX 4090, llama-server b10488-9d77fa172)

- **Serveur** : santé en 4–20 s (modèle en cache disque) ; VRAM 18 674 MiB
  (chat seul) / 19 046 MiB (avec `--embeddings`), gate 556 MiB inclus ;
  marge ~5,5 Go pour les rejeux CUDA de la porte.
- **Chat** : decode 47,3–47,6 t/s ; prefill 1 675 t/s (1 065 tokens en 636 ms,
  log serveur du run distiller) ; `model` rendu = `qwen-local` (l'alias).
- **Embeddings** (`-Embeddings`, `--pooling last`) : HTTP 200, dim 5120,
  0,38 s — et le chat sur la MÊME instance reste à 47,6 t/s : sur b10488,
  `--embeddings` ne dégrade pas la génération (mesuré, pas supposé). Opt-in
  conservé : aucun consommateur d'embeddings dans le harnais aujourd'hui
  (grep vide) ; l'index repo décidera du défaut.
- **Distillation** (session J10 réelle, `DISTILLER_URL` local, `--modele
  qwen-local`, sorties déviées vers des copies scratch) : 4 leçons écrites,
  0 refusée, 1 suspect correctement signalé, 16,5 s, **0,0000 USD**
  (campagne `phase5/distiller-local` au grand livre). Le DÉFAUT du distilleur
  reste OpenRouter : le passage du distilleur de fin de session au local est
  une décision de câblage nightly, explicitement hors de cet ordre.
- **Probation coder** (fumée PONG, préset minimal, enregistreur :8051 →
  amont 127.0.0.1:8004) : dsh rc=0 en 10,1 s, PONG.txt écrit, 3/3 appels
  `servi=qwen-local`, outils réellement appelés par le modèle, cache llama.cpp
  49 % puis 98 % entre runs, 0 USD. Verdict **VERT enregistré** dans
  `modeles.sqlite` : verts minimal = 1/3, probation = 1, tier = PRIVATE+OPEN.
  La probation se lèvera au 3ᵉ vert, comme pour un gratuit — la gratuité
  marginale ne dispense pas de faire ses preuves.

## Échec publié + zombie découvert

L'essai 1 de la probation a échoué : **7 appels en 404** dont le corps était
une page Vercel (`reports/phase5_qwen_local/probation1_echec_zombie.txt`).
Cause : un **enregistreur zombie** (`node proxy.mjs`, PID 4248, créé le 23/08
18:19 par un run fumée interrompu) tenait le port 8050 avec SON amont figé
(openrouter.ai) ; le proxy neuf ne pouvait pas se lier (stderr avalé) et la
sonde de santé prenait la réponse du zombie pour la sienne. `/v1/chat/completions`
sur openrouter.ai (au lieu de `/api/v1/...`) rend exactement cette 404 Vercel.
Les runs des 23–24/08 passaient par ce zombie **sans dégât** (même amont,
même chemin) ; la route locale l'a exposé. Corrections : bind-test du port
AVANT de lancer le proxy (refus bruyant nommant `FUMEE_PORT`), et la
validation a tourné sur `FUMEE_PORT=8051`. Le zombie est encore vivant
(l'arrêt d'un processus requiert la main de l'utilisateur) — à tuer :
`Stop-Process -Id 4248`.

Second accroc, corrigé : le relancement `-Embeddings` s'est refusé lui-même
(exit 2) — la garde GPU ne connaissait pas l'instance sortante sur :8004 que
l'étape d'arrêt allait remplacer. La garde admet désormais gate + llama-server
du port cible, et rien d'autre.

## Reste de la Phase 5 (non commencé)

- freellmapi en Docker (case 2) avec son ⚑ RT propre (ENCRYPTION_KEY, ToS,
  fuite PRIVATE).
- Migration des workers OPEN d'OpenRouter free vers les chaînes freellmapi.
- Critère Done de phase (⚑ RT payant) : travail OPEN à ~0 € marginal,
  distillation PRIVATE locale, OpenRouter réduit au planning — à re-mesurer
  quand la case 2 existera.
- Décision de câblage (utilisateur) : distilleur de fin de session sur le
  local par défaut, et politique de co-résidence serveur/porte pendant les
  campagnes.
