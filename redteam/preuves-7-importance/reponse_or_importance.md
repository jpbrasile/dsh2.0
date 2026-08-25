After reviewing the provided PIRT rankings against the physics headers, I find several misrankings that need correction. Here is my detailed analysis:

---

## Row-by-Row Analysis

### 1. `ozone.branche_n2a` — Importance: 3 → **TOO HIGH → 1**

**Physical argument:** The justification claims this is a "facteur MULTIPLICATIF direct du G-value (g/kWh), la metrique de sortie de tete." This is factually wrong based on the provided `ozone_3d.jl` header. The header describes standard O/O₃ chemistry tracking with O atom production from electron-impact dissociation of O₂ at ~6 eV, three-body O₃ formation, and wall loss. There is **no mention whatsoever** of N₂(A) metastables, no N₂(A) + O₂ → N₂ + 2O branching, and no `f` kwarg described. The header explicitly states the O atom source is "e + O₂ → e + O + O (dissociation at ~6 eV)" — a direct electron-impact channel, not an N₂(A) energy-transfer channel.

Furthermore, the stated primary QoI chain is **Ar\* → Ar₂\* → 126 nm VUV → O₂ photodissociation → O₃**, which is a photolytic pathway entirely distinct from any N₂(A) chemistry. The `ar_jet_chemistry_3d.jl` header confirms this: "Ar\* decays in ~0.13 µm via excimer formation (NOT Penning with O₂). The VUV channel bridges the spatial gap." N₂(A) is a species relevant to air plasmas (not Ar/He jets) and does not appear in any of the six provided source headers.

The `f` kwarg described in the justification is not evidenced in the `ozone_3d.jl` header. If it exists deeper in the file, it is a calibration factor, not a physical phenomenon. A calibration factor's uncertainty is not the same as the phenomenon's importance — this is a classic PIRT error (confusing parameter uncertainty with phenomenological importance). Even if N₂(A) chemistry exists elsewhere in the codebase, it is not part of the Ar jet VUV chain that defines the primary QoI.

**Proposed importance: 1** (support role at most, if present at all; the phenomenon as described does not match the QoI chain).

---

### 2. `amr.seuil_chimie_jet` — Importance: 1 → **AGREE**

**Physical argument:** The justification correctly identifies this as a numerical configuration parameter, not a physical phenomenon. The `adaptive_subcycle.jl` header confirms this is a state-machine transition criterion (`FrontPositionThreshold(z_fraction=0.85)`) for adaptive subcycling — it controls *when* chemistry is computed, not *what* chemistry occurs. The justification's note that "les chemins exerces l'ecrasent explicitement (mesure C4) et le defaut est verrouille par J14" indicates test coverage, and the residual risk (silent truncation of chemistry zone) is correctly characterized as low. A numerical threshold that is test-guaranteed does not become physically important just because misconfiguration could cause problems — that confuses code robustness with phenomenological importance. **Ranking 1 is correct.**

---

### 3. `pic_core.taux_penning_o2` — Importance: 2 → **TOO HIGH → 1**

**Physical argument:** The justification contains a critical configuration confusion. It states: "canal d'ionisation dominant en zone de melange pour les configurations jet He ; mais la chaine QoI de tete (jet Ar, phases 21-22) passe par l'excimere VUV, PAS par le Penning." This correctly identifies that the primary QoI chain is Ar-jet VUV, not He-jet Penning. However, it then assigns importance 2 ("significatif") anyway.

The `penning_ionization.jl` header is explicitly for **He plasma jets** — it tracks He\* metastables and He\* + O₂/N₂ Penning ionization. The `ar_jet_chemistry_3d.jl` header explicitly states: "Ar\* decays in ~0.13 µm via excimer formation (**NOT Penning with O₂**)" [emphasis in original]. The primary QoI is O₃ production via the Ar jet VUV chain. The Penning module is for a **different gas configuration** (He, not Ar). If the digital twin is configured for Ar jets (as the QoI chain indicates), the He Penning module may not even be active. If it is active in a He configuration, it feeds a different O₃ production pathway not prioritized in the stated QoI.

A phenomenon that is dominant for a configuration *not* matching the primary QoI chain should not be ranked "significant" for that QoI. **Proposed importance: 1** (relevant only if He jets are simulated; not on the primary Ar→VUV→O₃ chain).

---

### 4. `coupling.masse_electron` — Importance: 2 → **TOO LOW → 1 (or AGREE with corrected reasoning)**

**Physical argument:** The justification states: "Constante exacte sans incertitude : le risque est la coquille de code, pas la physique." This is a correct observation but leads to the wrong ranking. The PIRT principle is to rank *phenomena* by their importance to the QoI, not by their uncertainty. A constant with zero uncertainty that has large leverage on the QoI should be ranked high *because it matters*, not low because it's certain.

However, looking more carefully: m_e enters Q_el ~ (2m_e/M) as a *constant factor*. The electron mass is a fundamental constant — it is not a "phenomenon" subject to modeling choices, parametric uncertainty, or experimental validation. It is a fixed number hardcoded in the source. The `thermal_coupling.jl` header confirms `m_e = 9.10938e-31 kg` as a physical constant. Ranking fundamental constants in a PIRT is category error — PIRT ranks modelable physical processes (reaction rates, transport mechanisms, boundary conditions), not universal constants.

The gas temperature QoI is secondary, and the elastic collision heating mechanism *is* important for cold plasma applications. But the *electron mass specifically* is not a phenomenon — the *elastic collision heating mechanism* (Q_el) would be the proper PIRT entry. **Proposed importance: 1** (fundamental constant, not a phenomenon; the heating mechanism it participates in is what matters, and that would be ranked separately).

---

### 5. `ions_ar.alpha_dr_kcluster` — Importance: 2 → **TOO LOW → 3**

**Physical argument:** The justification states: "boucle de recyclage Ar+ -> Ar2+ -> Ar\* indispensable au mode rafale 1 MHz (sans elle : pas de puits electronique ni de retour Ar\*) ; nourrit la chaine VUV mais a un cran de la QoI -- significatif."

This understates the criticality. The `ar_ion_chemistry_3d.jl` header explicitly states: "Closes the Ar⁺ recycling loop needed for multi-pulse (burst 1 MHz) operation. **Without these reactions, Ar⁺ produced by PIC ionization is lost — no recombination sink for electrons, no Ar\* feedback from ion recombination.**" [emphasis added]

The primary QoI chain is Ar\* → Ar₂\* → VUV → O₃. The Ar\* that feeds this chain comes from two sources: (1) direct electron-impact excitation during the PIC pulse, and (2) dissociative recombination of Ar₂⁺ with electrons (Ar₂⁺ + e⁻ → Ar\* + Ar). In multi-pulse burst mode at 1 MHz, the inter-pulse Ar\* population is **entirely sustained** by the ion recombination loop. Without it, Ar\* density collapses between pulses, and the VUV/O₃ production ceases after the first pulse. The justification acknowledges this is "indispensable" (indispensable) yet ranks it only 2.

A phenomenon that is "indispensable" to the QoI chain in the operating regime (1 MHz burst mode) should be ranked 3 (critical). The "one step removed" argument is invalid because there is no alternative pathway — if this loop breaks, the entire Ar\* population vanishes in multi-pulse operation, and the QoI goes to near-zero. **Proposed importance: 3.**

---

### 6. `jet_ar.excimere_vuv` — Importance: 3 → **AGREE**

**Physical argument:** The justification correctly identifies this as the "key insight" and the sole spatial bridge between the Ar core and ambient O₂. The `ar_jet_chemistry_3d.jl` header confirms: "In a laminar Ar jet, the core is pure Ar. Ar\* decays in ~0.13 µm via excimer formation (NOT Penning with O₂). The VUV channel bridges the spatial gap — photons propagate freely through Ar and are absorbed by O₂ at the mixing boundary. This produces O₃ exclusively at the boundary, not on axis."

The excimer VUV pathway *defines* where and how much O₃ is produced. The lifetime τ (TAU_AR_JET_AR2) directly controls the spatial distribution of photon emission and thus the O₃ production zone. This is unambiguously critical to the primary QoI. **Ranking 3 is correct.**

---

## Verdict Table

| Row ID | Given | Yours | One-line reason |
|---|---|---|---|
| `ozone.branche_n2a` | 3 | **1** | N₂(A) not in any provided header; O atom source is e⁻ + O₂ dissociation per `ozone_3d.jl`; not on Ar→VUV→O₃ QoI chain; confuses calibration factor with phenomenon |
| `amr.seuil_chimie_jet` | 1 | **1** | AGREE — numerical threshold, not physical phenomenon; test-guaranteed default; correctly ranked as support |
| `pic_core.taux_penning_o2` | 2 | **1** | He-jet Penning module; `ar_jet_chemistry_3d.jl` explicitly states "NOT Penning with O₂"; wrong gas configuration for primary Ar-jet QoI |
| `coupling.masse_electron` | 2 | **1** | m_e is a fundamental constant, not a modelable phenomenon; PIRT ranks physical processes, not universal constants hardcoded in source |
| `ions_ar.alpha_dr_kcluster` | 2 | **3** | Header states "Without these reactions... no Ar\* feedback"; indispensable for multi-pulse 1 MHz operation; Ar\* population collapses without it → QoI goes to zero |
| `jet_ar.excimere_vuv` | 3 | **3** | AGREE — sole spatial bridge Ar core→O₂; controls where and how much O₃ forms; header confirms "key insight" |

---

## Factual Error in Justification

**`ozone.branche_n2a` justification:** "facteur MULTIPLICATIF direct du G-value (g/kWh), la metrique de sortie de tete ; un biais sur f biaise la QoI 1:1."

**Correction:** The `ozone_3d.jl` header describes O atom production via "e + O₂ → e + O + O (dissociation at ~6 eV)" — direct electron-impact dissociation, not N₂(A) energy transfer. No N₂(A) metastable chemistry, no `f` kwarg, and no G-value multiplier are described in the provided header. The primary QoI chain (Ar\* → Ar₂\* → 126 nm VUV → O₂ photodissociation → O₃) is a photolytic pathway documented in `ar_jet_chemistry_3d.jl`, not an N₂(A) pathway. If an `f` calibration factor exists, it is a tuning parameter, not a physical phenomenon — and parameter uncertainty ≠ phenomenological importance.