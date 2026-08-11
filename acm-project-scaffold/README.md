# ACM — Agentic Configuration Management (référence v0.1)

Implémentation de référence du **Lifecycle & State Propagation Model v0.1**, et
harness d'évaluation des scénarios expérimentaux pour l'article arXiv.

Le dépôt contient quatre couches :

1. le **noyau `acm/`** — modèle normatif (pydantic seul) qui représente un
   système agentique comme une configuration composite d'objets identifiables et
   versionnés, et propage qualité / assurance / impact / éligibilité ;
2. les **adaptateurs `adapters/` + le port `ports/`** — projettent LangGraph et
   CrewAI vers la sémantique ACM commune, derrière une frontière record/replay ;
3. le **harness `harness/`** — exécute des fixtures YAML déclaratives (config +
   evidence + oracle) contre le noyau et produit des rapports structurés
   reproductibles ;
4. les **scénarios** — cas d'étude historiques (`scenarios/scenario_*.py`) et
   fixtures d'évaluation S01..S27 (`scenarios/fixtures/*.yaml`).

---
```bash
pip install 'pydantic>=2' pyyaml pytest        # noyau + harness
# extras optionnels : pip install -e '.[langgraph,crewai]'

# Suite complète
PYTHONPATH=. python -m pytest tests/ -v
PYTHONPATH=. python -m pytest tests/ -q -p no:cacheprovider

# Harness seul (fixtures d'évaluation)
PYTHONPATH=. python -m pytest tests/test_scenarios.py tests/test_transitions.py -v

# Runner autonome : exécute scenarios/fixtures/*.yaml → rapport JSON (§4)
PYTHONPATH=. python run_evaluation.py --repeat 10 --out evaluation_report.json
```

`--repeat N` rejoue chaque scénario N fois et vérifie la stabilité des digests
(reproductibilité, §13.1 du plan).

```bash
# Génération du rapport de préservation
PYTHONPATH=. python generate_preservation_report.py

# Génération du rapport d'évaluation
PYTHONPATH=. python generate_evaluation_report.py

# Génération du rapport d'impact
PYTHONPATH=. python generate_impact_report.py

# Inspecter enfin le contenu de ._meth et .unwrap() — les deux boîtes noires restantes de CrewAi pour diganostic
PYTHONPATH=. python diagnose_meth.py

# Inspection du flow pour CrewAI (faut-il faire la même chose pour OpenAI?)
PYTHONPATH=. python diagnose_flow_wrappers_deep.py

# 1. Figer les oracles, puis générer le manifest à partir d'eux
PYTHONPATH=. python -c "from harness.oracle_provenance import build_manifest, save_manifest; save_manifest(build_manifest('scenarios/impact_experiment/oracle'), 'scenarios/impact_experiment/oracle_manifest.json')"

# 2. Commiter oracles + manifest ENSEMBLE, dans le même commit
git add scenarios/impact_experiment/oracle/ scenarios/impact_experiment/oracle_manifest.json
git commit -m "Freeze impact oracles + manifest (chaîne de preuve)"

# 3. Lancer l'expérience — les deux champs se remplissent automatiquement
PYTHONPATH=. python generate_impact_experiment_report.py \
    --oracle-dir scenarios/impact_experiment/oracle \
    --inspection-dir scenarios/impact_experiment/inspection \
    --manifest scenarios/impact_experiment/oracle_manifest.json \
    --out-dir docs

`̀`` 
---


## 2. Arborescence complète

```
.
├── README.md                          Ce fichier
├── pyproject.toml                     Package acm, deps, extras (dev/langgraph/crewai)
├── conftest.py                        Config pytest partagée
├── run_evaluation.py                  Runner autonome CLI → rapport JSON (§4)
│
├── acm/                               ── NOYAU NORMATIF (ne pas modifier sans raison) ──
│   ├── __init__.py                    API publique : propagate, modèles, enums, invariants
│   ├── invariants.py                  Invariants I1..I14 + check_report_invariants
│   ├── policy.py                      PropagationContext, EligibilityContext, Policy, ReleaseRules
│   │
│   ├── models/                        Modèles de données immuables (frozen)
│   │   ├── __init__.py
│   │   ├── aci.py                     ACIRevision, DeclaredStatus, Evidence, Relation,
│   │   │                              ConfigurationGraph, AssurancePolicy
│   │   ├── enums.py                   Enums normatifs + ordres de sévérité (worst_*)
│   │   ├── refs.py                    ACIRef (id + revision_id + digest), Reason,
│   │   │                              matches_revision(), canonical_ref_digest()
│   │   └── status.py                  ComputedStatus, ItemStatus, PropagationReport
│   │
│   ├── propagation/                   Moteur de propagation (stateless)
│   │   ├── __init__.py
│   │   ├── engine.py                  propagate() — point-fixe déterministe, ordre trié
│   │   ├── assurance.py               evidence_applicability, couverture, modes §16.2
│   │   ├── quality.py                 quality_from_evidence, agrégation worst-state
│   │   ├── impact.py                  impact_state (current/impacted/stale)
│   │   └── eligibility.py             eligibility_state par contexte (§12.3)
│   │
│   ├── runtime/                       Monde runtime (instances dynamiques, baselines)
│   │   ├── __init__.py
│   │   ├── baselines.py               Baseline + matrice de transitions §6.3 (déjà présente)
│   │   ├── instance.py                RuntimeInstanceStatus, DriftClassification
│   │   ├── evaluator.py               evaluate_runtime_instance (§20)
│   │   ├── governance.py              digest_of_resolved_config, résolution spec→config
│   │   ├── revisions.py               Aides de révision
│   │   ├── signal.py                  RuntimeSignal (frontière record/replay), ResolvedConfig
│   │   └── spec.py                    AgentSpec, PermissionCeiling
│   │
│   └── state_machines/                ── AJOUT : validation de transitions (additif) ──
│       ├── __init__.py                API publique du module
│       ├── machines.py                4 matrices pures §5.3/§6.3/§7.2/§8.4 (StateMachine)
│       └── validator.py               TransitionValidator strict/permissif + séquences runtime
│
├── ports/                            ── FRONTIÈRE ABSTRAITE (hexagonal) ──
│   ├── __init__.py
│   └── runtime_adapter.py             Interface RuntimeAdapter (contrat record/replay)
│
├── adapters/                         ── PROJECTIONS FRAMEWORK → ACM ──
│   ├── __init__.py
│   ├── langgraph_adapter.py           Extraction LangGraph → ConfigurationGraph
│   ├── crewai_adapter.py              Extraction CrewAI → ConfigurationGraph
│   └── deterministic_stub.py          Adaptateur figé (tests sans framework réel)
│
├── harness/                          ── HARNESS D'ÉVALUATION (fixtures → rapport) ──
│   ├── __init__.py                    API publique du harness
│   ├── loader.py                      YAML → objets acm (config, evidence, context, séquence)
│   ├── digest.py                      canonical_json + content/config/evidence digest (§4)
│   ├── asserter.py                    Rapport observé vs oracle, multi-niveaux, diff lisible
│   ├── runner.py                      Orchestration load→propagate→digest→assert, ScenarioResult §4
│   └── reporter.py                    Agrégation → EvaluationReport JSON pour l'article
│
├── scenarios/                        ── SCÉNARIOS (2 formes) ──
│   ├── __init__.py
│   ├── scenario_a.py                  Cas d'étude A (impératif, historique) — promotion nominale
│   ├── scenario_b.py                  Cas d'étude B
│   ├── scenario_c.py                  Cas d'étude C
│   ├── scenario_de.py                 Cas d'étude D et E
│   ├── scenario_f.py                  Cas d'étude F
│   └── fixtures/                      ── FIXTURES DÉCLARATIVES YAML (le harness) ──
│       ├── ACM-S01.yaml               Configuration nominale + baseline (P0)
│       ├── ACM-S03.yaml               Identité exacte : digest faux → inapplicable → blocked (P0)
│       └── ACM-S13.yaml               Séquence runtime invalide : completed→running (P0)
│
├── examples/                         ── DÉMOS EXÉCUTABLES ──
│   ├── __init__.py
│   ├── langgraph_demo.py              Run LangGraph réel → signal ACM
│   ├── crewai_demo.py                 Run CrewAI réel → signal ACM
│   └── records/                       Runs enregistrés (record/replay déterministe)
│
├── docs/                             Notes de spec, requirements updates (ex. I4/I5 v0.2)
│
└── tests/                            ── SUITE PYTEST ──
    ├── __init__.py
    ├── strategies.py                  Stratégies Hypothesis (graphes aléatoires)
    ├── test_core_no_extras.py         Le noyau importe sans langgraph/crewai
    ├── test_invariants.py             I1..I14
    ├── test_assurance_composition.py  Modes direct_only/aggregate_only/hybrid (§16.2)
    ├── test_config_digest.py          Stabilité du digest de configuration
    ├── test_p0_review.py              Revue des scénarios P0
    ├── test_p1_review.py              Revue des scénarios P1
    ├── test_p2_properties.py          Property-based (≈900 graphes)
    ├── test_scenario_a.py             Cas d'étude A..F (un fichier par cas)
    ├── test_scenario_b.py
    ├── test_scenario_c.py
    ├── test_scenario_de.py
    ├── test_scenario_f.py
    ├── test_langgraph_adapter.py      Extraction LangGraph
    ├── test_langgraph_execution.py    Run LangGraph réel (gpt) → digest identique
    ├── test_crewai_adapter.py         Extraction CrewAI
    ├── test_recorded_runs.py          Replay des runs enregistrés
    ├── test_scenarios.py              ★ Chaque fixture YAML = test paramétré + déterminisme
    └── test_transitions.py            ★ Matrices + TransitionValidator + séquences S13
```  

★ = ajoutés avec le harness. Le reste préexistait au noyau.

> **Convention d'import.** Certains modules de `runtime/` importent en `..models`
> (ex. `baselines.py`, `revisions.py`) : ils doivent rester sous `acm/` comme
> sous-package frère de `acm/models/`. Le harness suppose `acm` importable
> (`PYTHONPATH=.` ou `pip install -e .`).

---
## 3. Architecture — décisions verrouillées

Ces décisions ont été prises après audit du noyau existant. Les rappeler évite
de refaire le débat dans une session ultérieure.

### 3.1. Le noyau est *stateless* et le lifecycle est *intrinsèque*

`propagate(graph, evidence, context)` ne persiste rien : il prend un graphe et
retourne un `PropagationReport`. Le `lifecycle_state` d'une révision est une
propriété **intrinsèque** d'un objet `frozen`, **jamais** dérivée d'un journal
d'événements. C'est un choix normatif : ACM sépare l'état *déclaré* (intrinsèque)
de l'état *calculé* (dérivé). Le lifecycle déclaré ne doit pas être contaminé par
les dépendances (cf. S05).

### 3.2. Pas d'EventLog / pas de store append-only

Une architecture event-sourcing (EventLog comme source de vérité du lifecycle)
a été **explicitement écartée** : elle contredirait §3.1 et aucun des 27
scénarios ne l'exige. Ce qui est utile de cette idée — la *validation* de
transitions — a été conservé sans persistance (voir §3.4).

### 3.3. Identité : `revision_id` + `content_digest`

- `revision_id` = identité **métier** stable (ULID/UUIDv7), générée à la
  création. Vit dans `ACIRef`.
- `content_digest` = identité **matérielle**, dérivée du contenu canonique.

Une preuve cible `id` + `revision_id` + `content_digest` **simultanément**
(`ACIRef.matches_revision`, invariant I2). Règle de distinction :

| Divergence | Applicabilité | Réversible ? |
|---|---|---|
| `content_digest` cible ≠ recalculé | **invalid / inapplicable** | non (autre contenu) |
| snapshot de dépendances divergent | **stale** | oui (réanalyse) |
| `valid_until` dépassé | **stale** (expired) | oui (renouvellement) |

> Limite connue : dans le noyau actuel, `canonical_ref_digest` dérive le digest
> de `id@revision_id`, pas du contenu réel. Le vrai digest de contenu est
> fourni par `harness/digest.py::content_digest()`. C'est ce qui rend S03/S16
> vérifiables par hachage plutôt que par booléen posé à la main.

### 3.4. Validation de transitions sans persistance

`acm/state_machines/` ajoute :

- **4 matrices pures** (`StateMachine`) : lifecycle §5.3, baseline §6.3 (réutilise
  la matrice déjà dans `baselines.py`), runtime §7.2, promotion §8.4 ;
- **`TransitionValidator`** : `strict=True` lève `InvalidTransitionError` (code
  stable), `strict=False` marque et poursuit ;
- **validation de séquence runtime** : détecte les anomalies de S13
  (completed→running, terminaison avant instanciation, doublon, rupture de
  séquence) et signale le graphe reconstruit comme non fiable.

Aucun état stocké : le validateur répond, il ne mémorise pas.

### 3.5. Indépendance framework (`ports/` + `adapters/`)

Architecture hexagonale : `ports/runtime_adapter.py` définit le contrat, les
adaptateurs le projettent. La thèse centrale — LangGraph et CrewAI produisent le
**même `resolved_config_digest`** pour un système logiquement équivalent — est
vérifiée dans `test_langgraph_execution.py` et `test_crewai_adapter.py`.

---

## 4. Le harness — comment ça marche

### 4.1. Flux

```
scenarios/fixtures/ACM-Sxx.yaml
        │  loader.py     (YAML → ConfigurationGraph, Evidence, Context, [séquence runtime])
        ▼
   propagate()           (noyau, inchangé)
        │  digest.py      (configuration_digest, evidence_digest — métrique §4)
        ▼
   asserter.py           (rapport observé vs bloc `expected:` de la fixture)
        │
        ▼
   ScenarioResult (§4) ──► reporter.py ──► evaluation_report.json
```

### 4.2. Format d'une fixture

Chaque fichier `scenarios/*.yaml` contient :  
  
```yaml
scenario_id: ACM-S0x
priority: P0                     # P0 (article) | P1 | P2
frameworks: [core]
description: >
  ...
context:                         # optionnel — défauts déterministes
  eligibility_context: validation
  environment: local
  now: "2026-07-27T10:00:00Z"
revisions:                       # ACI : id, revision_id, type, états déclarés, policy
  - id: aci:agent:planner
    revision_id: R1
    aci_type: agent
    lifecycle_state: validated
    quality_state: ok
    assurance_state: assessed
    assurance_policy: {required_assurance_dimensions: [functional], composition_mode: direct_only}
relations: []                    # source/target par id logique, relation_type, policy
evidence:
  - id: evidence:eval:planner:001
    target: aci:agent:planner
    target_revision_id: R1
    target_digest: "sha256:..."  # peut être FAUX (S03)
    scope_dimensions: [functional]
    result: pass
    blocking: true
runtime_sequence: []             # optionnel (S12/S13)
expected:                        # ── ORACLE ──
  converged: true
  valid: false
  items:
    aci:agent:planner: {effective_assurance: unassessed, eligibility_state: blocked,
                        inapplicable_evidence: [evidence:eval:planner:001]}
  runtime_sequence: {valid: false, reliable: false, problem_codes: [ACM-TRANSITION-001]}
```

L'oracle peut asserter, par item : les 4 états calculés, `lifecycle_state`
(intrinsèque), `declared_*`, les `reason_codes` (existence), et la classification
des preuves (`applicable`/`stale`/`inapplicable`). Au global : `converged`,
`valid`, `max_iterations`, `graph_problems_contains`, et le bloc
`runtime_sequence`.

---

### 4.3. Ce que l'oracle peut asserter

Conformément à §13.4 du plan, l'asserter ne vérifie pas que l'état global. Par
item : `effective_quality`, `effective_assurance`, `impact_state`,
`eligibility_state`, `lifecycle_state` (intrinsèque), `declared_*`, les
`reason_codes` (existence, jamais le message), et la classification des preuves
(`applicable_evidence` / `stale_evidence` / `inapplicable_evidence`). Au global :
`converged`, `valid`, `max_iterations`, `graph_problems_contains`, et le bloc
`runtime_sequence`.

---

## 5. État d'avancement — couverture des 27 scénarios

| État | Scénarios | Ce qu'il reste |
|---|---|---|
| ✅ Fixture écrite | S01, S03, S13 | — |
| 🟢 Couvert par le noyau, fixture à écrire | S02, S05–S11, S18–S27 (≈19) | fixture YAML + oracle |
| 🟡 Débloqué par `state_machines/`, fixture à écrire | S04, S17 | fixture (transitions baseline) |
| 🟠 Runtime / adaptateurs | S12, S14–S16, S22–S24 | séquences + intégration adaptateurs |

**Ordre recommandé (§15 du plan) :** S02 puis groupe B (S05–S11), tous couverts
par le moteur tel quel. Puis S04/S17 (baseline). Puis runtime et adaptateurs.

### Réserves normatives à recouper avant publication

- Les transitions runtime §7.2 dans `machines.py` ont été reconstruites à partir
  de la machine à états standard décrite par le plan (journal S12) et de la
  sémantique §7. À **recouper avec le texte exact du PDF §7.1**.
- La matrice lifecycle §5.3 dans `machines.py` doit être confrontée à ce que
  `invariants.py` (I3) suppose, pour garantir la cohérence.

---

## 6. Métrique de résultat (§4 du plan)

Chaque scénario produit un `ScenarioResult` sérialisé :

```json
{
  "scenario_id": "ACM-S03",
  "framework": "core",
  "priority": "P0",
  "configuration_digest": "sha256:...",
  "evidence_digest": "sha256:...",
  "expected_status": {},
  "observed_status": {},
  "invariants_checked": ["I1", "...", "I14"],
  "invariants_violated": [],
  "runtime_event_count": 0,
  "propagation_iterations": 2,
  "converged": true,
  "execution_time_ms": 0.5,
  "result": "pass",
  "mismatches": []
}
```

`execution_time_ms` est purement diagnostique et **exclu de toute assertion**
(il n'affecte pas le déterminisme).

---

## 7. Pour reprendre dans une autre conversation

Points d'entrée utiles à re-fournir :

- `acm/__init__.py` — tout ce que le noyau expose.
- `acm/models/refs.py` — l'identité (`ACIRef.matches_revision`).
- `acm/propagation/engine.py` — le point-fixe.
- `acm/state_machines/` (2 modules) — la validation de transitions.
- `harness/` (5 modules) — le moteur d'évaluation.
- `ports/runtime_adapter.py` + un adaptateur — la frontière framework.
- Une fixture (`scenarios/fixtures/ACM-S03.yaml`) comme gabarit.
- Ce README (décisions §3, format §4, couverture §5).

**Règle d'or :** le noyau `acm/` ne se modifie pas pour ajouter un scénario. On
écrit une fixture dans `scenarios/fixtures/`. Toute capacité manquante s'ajoute
de façon **additive** (comme `state_machines/`), sans toucher au moteur validé.
  
---  


## Principe d'architecture

- `acm/` — cœur normatif, **zéro dépendance** à un framework agentique.
  Point d'entrée : `propagate(config, evidence, context, policy, strict) -> report`.
- `acm/runtime/` — évaluation des instances dynamiques (§20), `RuntimeSignal`,
  `AgentSpec`, et helpers de gouvernance partagés par tous les adaptateurs.
- `acm/invariants.py` — invariants normatifs I1→I14 (§23), critère de conformité §28.
- `acm/state_machines/` — machines à états : révisions (§5, §19.1), baselines (§6).
- `ports/` — interface `RuntimeAdapter` : frontière étanche exécution/gouvernance.
- `adapters/` — stub déterministe, **LangGraph**, **CrewAI** (même contrat).
- `scenarios/` — fixtures des scénarios normatifs A→F.
- `examples/` — démos exécutables LangGraph & CrewAI (gpt-5.4).
- `tests/` — un test par scénario + I1→I14 + équivalence inter-adaptateurs + record/replay.

## Frontière exécution / gouvernance

Le déterminisme est une propriété du **cœur**, pas de l'adaptateur. Un adaptateur
réel (LangGraph/CrewAI) sera non-déterministe à l'exécution, mais produit un
`RuntimeSignal` normalisé — sérialisable JSON — que le cœur traite de façon
déterministe. Record/replay : `signal.to_record()` / `RuntimeSignal.from_record()`.
Chaque signal porte un `resolved_config_digest` canonique (§3.5, I2), identique
quel que soit l'adaptateur.

## Équivalence inter-adaptateurs (thèse du projet)

Un MÊME `AgentSpec` produit un verdict de gouvernance IDENTIQUE et un digest
IDENTIQUE via les trois voies : stub déterministe, LangGraph, CrewAI. C'est la
démonstration mécanique que le paradigme ACM est indépendant du framework. La
logique de gouvernance vit dans le cœur (`acm/runtime/governance.py`) ; chaque
adaptateur reste mince (construction/exécution côté framework uniquement).

## État actuel

- [x] Modèles Pydantic (états, ACI, relations, preuves, graphe)
- [x] Moteur `propagate()` : quality / assurance / impact / eligibility
- [x] Assurance de composition : règle des 3 cas §16.2 (hybrid/aggregate/direct)
- [x] Machines à états : révisions (§19.1), baselines (§6 + statut opérationnel §6.5)
- [x] Évaluation runtime §20 + port `RuntimeAdapter` + stub déterministe
- [x] Scénarios A→F (§24.1 à §24.6) — tous testés
- [x] Invariants I1→I14 (§23) — assertions réutilisables + mode strict
- [x] Adaptateur LangGraph : couche 1 (construire+inspecter) & couche 2 (gpt-5.4 + record)
- [x] Adaptateur CrewAI : couche 1 & couche 2 (gpt-5.4 + record)
- [x] Équivalence à trois voies (stub / LangGraph / CrewAI) + digest partagé
- [x] Tests property-based P2 (Hypothesis) : convergence, idempotence,
  invariance à l'ordre, monotonie, stabilité de sérialisation (~900 graphes générés)
- [x] Renforcements P1 (revue) : preuves multiples couvrant R(x), preuves
  expirées, détection de cycles interdits (§21.4), indépendance de l'ordre,
  convergence/non-convergence explicite
- [x] Corrections normatives P0 (revue technique) : identité des preuves
  (id+revision_id+digest), staleness par snapshot, environnement,
  politique d'assurance optionnelle, qualité dérivée des preuves,
  intégrité du graphe, contrat de données (frozen / extra=forbid / enums),
  rapport enrichi (preuves applicables/stale/inapplicable, itérations, convergence)

## Installation

Recommandé : un environnement virtuel (venv ou conda), Python 3.11+.

    python -m venv .venv && source .venv/bin/activate
    # ou : conda create -n acm python=3.11 && conda activate acm

Installer le cœur seul (aucune dépendance framework) :

    pip install -e .

Installer avec un framework précis :

    pip install -e ".[langgraph]"          # LangGraph
    pip install -e ".[crewai]"             # CrewAI
    pip install -e ".[openai]"             # exécution réelle OpenAI (gpt-5.4)

Tout installer (les deux frameworks + exécution OpenAI + pytest) :

    pip install -e ".[all]"

### Note d'installation CrewAI

**Version de Python.** CrewAI exige `>=3.10,<3.14` (comme une grande partie de
l'écosystème ML : tiktoken, chromadb...). Si l'environnement tourne en Python
**3.14**, pip refuse toutes les versions récentes de CrewAI et se rabat sur de
très anciennes, avec le message `Could not find a version that satisfies
crewai>=1`, souvent accompagné d'un `Failed building wheel for tiktoken`
(aucune wheel précompilée pour 3.14 -> compilation depuis les sources -> échec).

La solution est d'utiliser **Python 3.13** (ou 3.11/3.12) :

    conda deactivate
    conda create -n acm python=3.13
    conda activate acm
    pip install -e ".[all]"

Le projet déclare `requires-python = ">=3.11,<3.14"` : l'incompatibilité est
donc signalée dès l'installation du cœur, avant même d'ajouter CrewAI.

Pour vérifier la version active :

    python --version

**PyJWT.** Sur certains systèmes où des paquets sont gérés par l'OS, il peut
être nécessaire de forcer la réinstallation de `PyJWT` :

    pip install -e ".[crewai]" --ignore-installed PyJWT

**websockets.** Si LangGraph et CrewAI sont installés ensemble, un avertissement
de version sur `websockets` peut apparaître (langgraph-sdk vs crewai) ; il est
sans effet sur le cœur ACM et les adaptateurs, qui n'utilisent pas le SDK
LangGraph distant.

## Tests

    pytest tests/ -v

137 tests : 6 scénarios normatifs, 14 invariants, adaptateurs LangGraph & CrewAI
(couches 1 & 2), équivalence à trois voies, digest de config canonique,
record/replay, comparaison de records inter-adaptateurs, déterminisme.
Tous exécutables **sans clé API** (modèles mockés).

## Exécution réelle (gpt-5.4)

    export OPENAI_API_KEY=sk-...
    PYTHONPATH=. python examples/langgraph_demo.py
    PYTHONPATH=. python examples/crewai_demo.py

Chaque démo construit un `AgentSpec` conforme, l'exécute réellement, enregistre
le `RuntimeSignal` en JSON (record), le fait évaluer par le cœur, puis rejoue le
signal figé sans réexécution. Les deux démos partent du MÊME spec et produisent
le MÊME verdict et le MÊME digest.

Les records sont écrits dans `examples/records/`. Le test `tests/test_recorded_runs.py`
compare automatiquement les deux records : digest de config identique, digests de
références identiques, et différences limitées à `adapter_name`/`produced_at`.

## Les deux adaptateurs

Même port `RuntimeAdapter`, deux couches :

**Couche 1 — construire + inspecter** (aucune clé API) : `create_instance(spec)`
construit un vrai objet framework (graphe LangGraph / Agent CrewAI) à partir d'un
`AgentSpec` pour prouver que la config est instanciable, puis produit un
`RuntimeSignal`. Sert aux scénarios D/E.

**Couche 2 — exécution réelle** (`execute(...)`) : lance le graphe/crew avec
gpt-5.4, reporte l'état terminal, et fige le signal en JSON (record) pour rejeu
déterministe. Le contenu métier (réponses LLM) ne traverse jamais la frontière :
seule la gouvernance (config résolue, traçabilité, permissions, état terminal)
passe.

## Exécution du cœur sans extras (P0-10)

Le cœur `acm/` n'a **aucune** dépendance framework et s'importe/s'exécute avec
`pip install -e .` seul. Les tests d'adaptateurs (LangGraph, CrewAI) sont
protégés par `pytest.importorskip` : ils sont **skippés** proprement si l'extra
correspondant n'est pas installé, sans faire échouer la suite. Le comptage de
tests dépend donc des extras présents :

    pip install -e .            # cœur seul : les tests d'adaptateurs sont skippés
    pip install -e ".[all]"     # tout : la suite complète s'exécute

Le test `tests/test_core_no_extras.py` vérifie explicitement que le cœur
(propagation + invariants + évaluation runtime) fonctionne frameworks absents.

## Note normative I4 / I5

La revue technique a relevé que la spec §23 énonce I4/I5 sur les états
**effectifs**, alors que l'implémentation les vérifie sur les états **déclarés**.
Ce choix est délibéré et documenté dans `docs/requirements_update_I4_I5.md` :
vérifier l'effectif contredirait le §3.4 (un composite validé dont la qualité
effective devient nok par propagation illustre le comportement correct, pas une
violation). La note propose de reformuler I4/I5 sur le déclaré dans une v0.2.

## Tests property-based (P2)

Le lot P2 utilise Hypothesis pour générer des centaines de graphes ACM valides
(DAG feuilles → agents → workflow) et chercher activement des contre-exemples
aux propriétés fondamentales du moteur :

- **convergence** — tout graphe valide atteint un point fixe ;
- **idempotence** — re-propager ne change pas les états ;
- **invariance à l'ordre** — l'ordre d'insertion n'affecte pas le résultat ;
- **monotonie** — dégrader une entrée ne peut qu'aggraver (jamais améliorer)
  les états effectifs ; propriété non vacative (exercée dans ~82% des cas) ;
- **stabilité de sérialisation** — round-trip JSON du rapport préservé.

    pip install -e ".[dev]"    # inclut hypothesis
    pytest tests/test_p2_properties.py -v

Les stratégies de génération sont dans `tests/strategies.py`. Le test est
protégé par `pytest.importorskip("hypothesis")`.
