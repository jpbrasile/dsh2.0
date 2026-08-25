**Verdicts and physical arguments**

---

### 1. `ozone.branche_n2a` — importance 3 → **TOO LOW? No, TOO HIGH**  
**Proposed importance: 2 (significant)**  

**Physical argument:**  
The primary QoI is O₃ production via the **Ar* → Ar₂* → VUV → O₂ photodissociation** chain. The `ozone_3d.jl` header describes generic O/O₃ chemistry (e‑impact dissociation, three‑body formation) and makes no mention of N₂(A). The parameter `f` is a keyword argument of the *N₂(A) branch*, i.e. it scales only the contribution of that secondary pathway. The justification incorrectly claims *“biaise la QoI 1:1”* — a bias in `f` propagates proportionally to the N₂(A) sub‑yield, not to the total ozone yield, because the dominant VUV channel is independent of `f`. The N₂(A) pathway is a supporting mechanism in air plasmas, not the critical Ar‑excimer chain.  

**Factual error in justification:**  
> *“facteur MULTIPLICATIF direct du G-value (g/kWh), la metrique de sortie de tete ; un biais sur f biaise la QoI 1:1.”*  
**Correction:** `f` is a branch‑specific multiplier for the N₂(A) contribution; it does **not** multiply the total G‑value 1:1. The total ozone yield is dominated by the VUV photodissociation pathway, which is independent of `f`.

---

### 2. `amr.seuil_chimie_jet` — importance 1 → **TOO LOW**  
**Proposed importance: 2 (significant)**  

**Physical argument:**  
The threshold `z_chemistry_fraction` controls **where** the jet chemistry (including the O₃‑producing mixing boundary) is computed. If set incorrectly, it can silently truncate the chemistry zone, directly removing the spatial region where O₃ forms. This is a numerical parameter with high impact on the primary QoI. The justification confuses *uncertainty* (locked by tests) with *importance*: a well‑known parameter can still be critical if its mis‑specification destroys the QoI.  

**No factual error in the justification text itself**, but the ranking under‑rates the phenomenon’s influence.

---

### 3. `pic_core.taux_penning_o2` — importance 2 → **AGREE**  

**Physical argument:**  
The Penning rate `K_PENNING_O2` is the dominant ionisation channel in **He** jets, but the primary QoI is defined for the **Ar** jet via the excimer VUV chain. The `ar_jet_chemistry_3d.jl` header explicitly states *“Ar* decays … via excimer formation (NOT Penning with