# Conclusion générale

L’implémentation a franchi un cap important : elle constitue désormais un **prototype de référence cohérent**, doté d’un noyau déterministe, d’un modèle de propagation, de machines à états, d’un harness déclaratif et d’une couverture fonctionnelle étendue.

Elle est suffisamment avancée pour soutenir un article arXiv centré sur :

- le métamodèle ACM ;
- la séparation des états intrinsèques et calculés ;
- la gestion des baselines ;
- la propagation d’assurance, d’impact et d’éligibilité ;
- la gouvernance des agents dynamiques ;
- la normalisation des signaux runtime.

En revanche, le dépôt ne permet pas encore de soutenir sans qualification les affirmations suivantes :

> « Les 27 scénarios sont tous expérimentalement validés. »

> « La portabilité LangGraph/CrewAI est démontrée. »

> « Le passage à l’échelle jusqu’à 1 000 ACI est reproductiblement établi. »

> « Le noyau n’a subi aucune modification. »

Le problème principal n’est plus la qualité du modèle, mais la **chaîne de preuve expérimentale** entre les scénarios, les tests exécutés, les données brutes, le rapport consolidé et les affirmations de l’article.

---

# 1. Résultat de l’exécution indépendante

J’ai exécuté la suite telle qu’elle est livrée dans l’archive.

```text
224 passed
7 skipped
durée : environ 1 seconde
```

Le runner autonome produit :

```text
11/11 fixtures passées
10 scénarios P0
1 scénario P1
14 invariants référencés
```

Cela confirme plusieurs points positifs :

- le dépôt est exécutable ;
- les tests du noyau passent ;
- le harness fonctionne ;
- les 11 fixtures déclaratives convergent ;
- les scénarios locaux ne nécessitent aucun appel LLM ;
- la séparation entre le noyau et les dépendances optionnelles fonctionne ;
- les invariants I1–I14 sont effectivement représentés dans le code et les tests.

Mais ces résultats ne correspondent plus aux chiffres du rapport consolidé :

| Élément | Rapport | Exécution constatée |
|---|---:|---:|
| Tests passés | 220 | **224** |
| Tests ignorés | 3 | **7** |
| Fixtures du rapport JSON | 11 | **11** |
| Scénarios dans le rapport consolidé | 27 | 27 annoncés |
| Scénarios frameworks réellement exécutés ici | annoncés conformes | **ignorés faute de dépendances** |

Le rapport est donc déjà **désynchronisé de la version livrée du dépôt**.

---

# 2. Analyse de l’architecture technique

## 2.1. Points forts

### Un noyau conceptuellement propre

La structuration du package `acm/` est pertinente :

```text
models/
propagation/
runtime/
state_machines/
invariants.py
policy.py
```

Elle reflète correctement les grandes dimensions du modèle :

- représentation de la configuration ;
- calcul des états ;
- invariants ;
- lifecycle ;
- runtime ;
- gouvernance des instances dynamiques.

La séparation entre :

```text
declared status
computed status
```

est bien matérialisée dans le code. Elle correspond à l’une des décisions conceptuelles les plus importantes du modèle ACM : ne pas modifier destructivement l’état intrinsèque d’un composite lorsque l’une de ses dépendances se dégrade.

### Des contrats de données restrictifs

Les modèles Pydantic utilisent largement :

```python
extra="forbid"
```

et, pour les révisions et preuves :

```python
frozen=True
```

Cela limite les erreurs silencieuses de structure et soutient l’objectif de configuration explicite.

### Un moteur déterministe

Le moteur :

- initialise les états locaux ;
- classe les preuves ;
- calcule l’assurance directe ;
- propage qualité, assurance et impact ;
- recalcule l’éligibilité ;
- itère jusqu’au point fixe ;
- utilise un ordre trié pour réduire la dépendance à l’ordre d’entrée.

Cette architecture est appropriée pour soutenir les propriétés de déterminisme et de convergence.

### Une bonne frontière runtime

Le port `RuntimeAdapter` et le `RuntimeSignal` constituent une bonne décision d’architecture.

Le noyau ne reçoit pas un objet LangGraph ou CrewAI natif. Il reçoit une représentation normalisée contenant notamment :

- définition source ;
- configuration résolue ;
- digest ;
- traçabilité ;
- permissions ;
- état terminal ;
- résultats des contrôles runtime.

C’est une base crédible pour défendre l’indépendance du **modèle ACM** vis-à-vis d’un framework particulier.

### Une bonne stratégie record/replay

Le choix de ne pas inclure les sorties probabilistes du LLM dans le chemin de validation est judicieux. Il permet de tester :

- la configuration résolue ;
- la provenance ;
- la conformité ;
- les permissions ;
- l’état terminal ;

sans prétendre rendre déterministe le comportement sémantique du modèle.

---

## 2.2. Limites techniques importantes

### A. Le moteur de propagation est peu efficace sur les grands graphes

Les calculs parcourent fréquemment les relations pour rechercher les dépendances d’un objet. Le coût pratique ressemble à :

\[
O(k \times |V| \times |E|)
\]

où \(k\) est le nombre d’itérations du point fixe.

Cela explique les valeurs annoncées dans le rapport :

```text
100 ACI / 300 relations      ≈ 92 ms
1 000 ACI / 3 000 relations  ≈ 8 100 ms
```

Une multiplication par dix du graphe produit presque une multiplication par cent du temps.

La correction principale serait de construire une fois :

```text
outgoing_relations_by_source
incoming_relations_by_target
relations_by_type
```

Le coût pourrait alors se rapprocher de :

\[
O(k \times (|V|+|E|))
\]

pour les propagations usuelles.

Cette optimisation n’est pas nécessaire avant un premier preprint si le périmètre déclaré reste celui de centaines d’ACI. Elle devient nécessaire pour revendiquer une utilisation à l’échelle d’une plateforme d’entreprise.

---

### B. L’immuabilité des baselines est principalement logique

Le commentaire du code de digest précise en substance que la baseline n’est pas nécessairement `frozen` en mémoire et que la modification est détectée par recalcul du digest.

Il faut donc distinguer :

1. **prévention de mutation** ;
2. **détection de mutation** ;
3. **persistance immuable**.

Le prototype apporte surtout le deuxième niveau.

La formulation correcte dans l’article serait :

> Released baselines are content-addressed and tamper-evident in the reference implementation.

Il serait excessif d’écrire :

> Released baselines cannot be modified.

sans stockage append-only, contrôle d’écriture ou objet effectivement immuable.

---

### C. La validité structurelle n’est pas intégrée à l’éligibilité

S02 révèle une séparation insuffisamment finalisée :

```text
référence requise absente
→ graph_problems détecté
→ configuration invalide
```

mais :

```text
ACI concerné
→ eligibility = eligible
```

Le mode strict empêche finalement l’usage de la configuration, mais le rapport d’état local reste contradictoire pour un lecteur ou un outil consommateur.

Ce n’est pas seulement une divergence du plan. C’est un **gap du modèle calculatoire actuel**.

La règle recommandée est :

\[
requiredReferenceMissing(x)
\Rightarrow
eligibility(x)=blocked
\]

avec une raison structurée telle que :

```text
ACM-REF-UNRESOLVED
```

La validité globale et l’éligibilité locale peuvent rester deux concepts distincts, mais elles doivent être reliées lorsque l’erreur structurelle est directement attribuable à un ACI.

---

### D. Les overrides interdits ne produisent pas un blocage dur

S20 montre que le moteur détecte l’override interdit, mais produit :

```text
assurance = unassessed
eligibility = warning
```

alors que le plan prévoit :

```text
eligibility = blocked
```

Pour les champs comme :

- outils autorisés ;
- identité du modèle ;
- politiques ;
- permissions ;
- factory source ;

un warning est trop faible. Un agent dynamique modifiant un champ explicitement non surchargeable doit être non éligible.

La règle devrait être :

\[
forbiddenOverride(i)
\Rightarrow
eligibility(i)=blocked
\]

La distinction warning/blocage peut dépendre du type de champ :

| Override | Traitement recommandé |
|---|---|
| description ou label non comportemental | information ou warning |
| purpose dans la liste autorisée | autorisé |
| prompt autorisé par la factory | réévaluation selon politique |
| outil non autorisé | blocked |
| modèle hors allowlist | blocked |
| politique supprimée ou remplacée | blocked |
| permissions supérieures | blocked + violation I13 |

---

### E. La taxonomie de drift n’est pas encore un résultat de premier ordre

L’approche retenue pour S14–S16 est conceptuellement raisonnable :

- `drift_state` minimal ;
- classification détaillée dérivée ;
- conformité de configuration séparée.

Mais cette classification semble vivre essentiellement dans le harness et les tests, non dans un contrat normatif central suffisamment riche.

Pour l’article, il faudrait formaliser au moins :

```text
runtime_extension_status
traceability_status
configuration_conformity
```

Par exemple :

```json
{
  "runtime_extension_status": "declared_extension",
  "traceability_status": "traceable",
  "configuration_conformity": "mismatch",
  "drift_state": "none"
}
```

Cela évite de faire porter au seul mot `drift` des phénomènes différents.

---

### F. Les identifiants de rapports empêchent une identité byte-for-byte

Le moteur génère notamment un `report_id` aléatoire par UUID, et certains artefacts incluent des timestamps.

Les **états fonctionnels et digests de configuration** peuvent être déterministes, mais les rapports complets ne sont donc pas identiques octet pour octet entre deux exécutions.

L’article et le rapport doivent préciser :

> Determinism applies to normalized states, canonical configuration/evidence digests, convergence and replay results, excluding non-semantic metadata such as report identifiers and generation timestamps.

---

# 3. Analyse du harness et des scénarios

## 3.1. Une bonne approche déclarative, mais seulement pour 11 scénarios

Le harness YAML est une très bonne contribution pratique :

```text
configuration
evidence
context
expected oracle
```

Il permet de séparer :

- les données du scénario ;
- l’exécution ;
- l’oracle ;
- le reporting.

Cependant, seulement 11 scénarios passent par cette chaîne unifiée :

```text
S01, S02, S03,
S05, S06, S07, S08, S09, S10, S11,
S13
```

Les 16 autres reposent sur des tests Python dédiés.

Ce n’est pas incorrect, car plusieurs scénarios ne relèvent pas directement de `propagate()`. Mais cela signifie que le runner autonome et son `evaluation_report.json` ne représentent pas l’évaluation consolidée.

Actuellement :

```text
evaluation_report.json = rapport des 11 fixtures
```

et non :

```text
evaluation_report.json = résultats structurés des 27 scénarios
```

Il manque donc une couche d’agrégation machine-readable.

### Recommandation

Créer un registre unique :

```json
{
  "scenario_id": "ACM-S18",
  "execution_mode": "dedicated_test",
  "test_nodes": [
    "tests/test_scenarios_group_d.py::test_s18_..."
  ],
  "status": "pass",
  "evidence_artifacts": [],
  "observations": {},
  "deviations": []
}
```

Puis générer le Markdown consolidé **à partir de ce JSON**, et non manuellement.

---

## 3.2. « 27/27 couverts » n’équivaut pas à « 27/27 conformes »

Le rapport donne à chaque scénario le statut `Conforme`, y compris :

- S02, dont l’éligibilité observée ne correspond pas au plan ;
- S20, où warning remplace blocked ;
- S22–S23, dont les tests ont été ignorés dans l’environnement audité.

Il faut utiliser une classification plus rigoureuse :

```text
PASS
PASS_WITH_DEVIATION
PARTIAL
SKIPPED
FAIL
NOT_EXECUTED
```

Je classerais actuellement :

| Scénario | Statut recommandé |
|---|---|
| S02 | `PASS_WITH_DEVIATION` |
| S14–S16 | `PASS_WITH_MODEL_REFINEMENT` |
| S20 | `PASS_WITH_DEVIATION` |
| S22 | `NOT_REPRODUCED_IN_CURRENT_ENVIRONMENT` |
| S23 | `NOT_REPRODUCED_IN_CURRENT_ENVIRONMENT` |
| S27 | `PARTIAL_BENCHMARK_EVIDENCE` |

Le terme « conforme » doit être réservé à une correspondance complète avec l’oracle normatif retenu.

---

## 3.3. La couverture inter-framework n’est pas démontrée par l’archive seule

Les tests réellement ignorés sont :

```text
CrewAI adapter
LangGraph adapter
LangGraph execution
Hypothesis
2 tests S22
1 test S23
```

Soit **7 skips**, et non 3.

Les deux tests S22 appellent explicitement :

```python
pytest.importorskip("crewai")
pytest.importorskip("langgraph")
```

Le test S23 nécessite LangGraph.

Dans l’environnement audité, la portabilité inter-framework n’a donc pas été exécutée.

Le rapport affirme que les scénarios ont été exécutés dans un environnement contenant les extras. C’est possible, mais l’archive ne contient pas :

- le log de cette exécution ;
- un rapport JUnit ;
- un fichier d’environnement ;
- un lockfile ;
- une CI attestant l’installation des deux frameworks ;
- les versions exactes utilisées.

L’affirmation n’est donc pas actuellement **audit-proof**.

### À ajouter

Une CI avec au minimum :

```text
Python 3.11
Python 3.12
core-only
core + hypothesis
core + LangGraph
core + CrewAI
core + LangGraph + CrewAI
```

et conservation des artefacts :

```text
pytest.xml
environment.txt
pip freeze
evaluation_report.json
benchmark_results.json
```

---

## 3.4. Les adaptateurs montrent surtout l’instanciabilité minimale

L’adaptateur LangGraph construit un graphe minimal :

```text
START → un nœud agent → END
```

Cette expérience prouve que la configuration résolue peut être câblée dans un objet LangGraph.

Elle ne démontre pas encore :

- l’extraction automatique d’un graphe LangGraph arbitraire ;
- l’import de transitions conditionnelles ;
- la conservation des sous-graphes ;
- la représentation de branches et boucles ;
- l’import des checkpointers ;
- le mapping des configurations distribuées ;
- l’équivalence de topologies complexes.

De même, l’équivalence de digest entre deux adaptateurs à partir du **même `AgentSpec` déjà normalisé** démontre surtout que les deux adaptateurs respectent une frontière commune. Elle ne démontre pas encore qu’ACM sait extraire automatiquement une configuration équivalente depuis deux applications natives indépendantes.

La revendication correcte est donc :

> The adapters demonstrate that a common ACM runtime specification can be instantiated in, and normalized across, LangGraph and CrewAI for the evaluated minimal cases.

Pas encore :

> ACM automatically extracts framework-independent configurations from arbitrary LangGraph and CrewAI systems.

---

# 4. Analyse spécifique de `evaluation_report_consolidated_v0.1.md`

## 4.1. Ce qui est bon

Le document possède plusieurs qualités notables :

- organisation claire par groupes de scénarios ;
- transparence sur S02, S14–S16 et S20 ;
- distinction entre fixtures et tests dédiés ;
- section consacrée aux limites ;
- correspondance scénarios–invariants ;
- absence de prétention à une validation probabiliste des sorties LLM ;
- reconnaissance explicite des limites d’échelle ;
- reconnaissance du périmètre limité de la portabilité.

Le rapport est nettement supérieur à un simple tableau « tous les tests passent ».

---

## 4.2. Ce qui doit être corrigé avant utilisation scientifique

### Les métriques sont obsolètes

Le rapport annonce :

```text
220 passed, 3 skipped
```

L’archive produit :

```text
224 passed, 7 skipped
```

Il faut générer automatiquement ces valeurs.

### « Modifications du noyau : 0 » n’est pas démontrable

Le document affirme :

```text
Modifications du noyau acm/ : 0
Extensions additives : state_machines/, conformité runtime
```

Or `state_machines/` se trouve précisément sous `acm/`.

On peut dire :

> No existing propagation module had to be modified to support the additional transition-validation scenarios.

Mais on ne peut pas conclure « zéro modification du noyau » sans :

- dépôt Git ;
- commit de référence ;
- diff ;
- définition explicite de ce qui constitue le noyau.

L’ajout de `acm/state_machines/` est bien une extension du package central, même si elle ne modifie pas les fichiers préexistants.

### Les temps ne sont pas suffisamment traçables

Les valeurs S01–S13 et S27 sont intégrées au Markdown, mais le rapport JSON régénéré ne contient que les fixtures exécutées lors du dernier lancement. Il n’existe pas de fichier brut consolidé permettant de relier :

```text
machine
Python
OS
CPU
versions
commande
répétitions
médiane
dispersion
résultat
```

Les valeurs de performance ne sont pas encore des résultats expérimentaux publiables.

### S27 n’est que partiellement automatisé

Les tests du dépôt vérifient principalement :

```text
100 ACI / environ 300 relations
temps < 5 secondes
```

Ils ne vérifient pas automatiquement les chiffres annoncés pour :

```text
1 000 ACI / 3 000 relations
5 000 ACI
```

Il faut ajouter un script de benchmark séparé. Les benchmarks ne devraient pas être des tests unitaires à seuil strict, mais produire des mesures répétées.

### L’expression « 14/14 invariants vérifiés » est ambiguë

Deux interprétations doivent être séparées :

1. chaque invariant possède au moins un test ;
2. chaque scénario satisfait tous les invariants applicables.

Le rapport mélange parfois couverture et satisfaction.

Une meilleure table serait :

| Invariant | Implémenté | Cas positif | Cas négatif | Scénarios applicables | Statut |
|---|---:|---:|---:|---|---|
| I1 | oui | oui | oui | S07 | couvert |
| I2 | oui | oui | oui | S03, S07 | couvert |
| … | … | … | … | … | … |

---

# 5. Qualité documentaire et reproductibilité du dépôt

## Problèmes de packaging

`README.md` demande :

```bash
pip install pydantic pyyaml pytest
```

mais `PyYAML` n’est pas déclaré dans `pyproject.toml`, y compris dans les dépendances `dev`.

Une installation :

```bash
pip install -e '.[dev]'
```

ne garantit donc pas que le harness fonctionne.

Il faut ajouter par exemple :

```toml
dev = [
  "pytest>=8",
  "hypothesis>=6",
  "pyyaml>=6"
]
```

ou définir un extra :

```toml
evaluation = ["pytest>=8", "hypothesis>=6", "pyyaml>=6"]
```

## Pas de versions verrouillées

Les extras utilisent :

```text
langgraph>=1
crewai>=1
```

Pour une expérimentation scientifique, cela est insuffisant. Une évolution future du framework peut changer les résultats.

Il faut conserver :

- un `requirements-lock.txt` ou `uv.lock` ;
- les versions exactes utilisées ;
- le hash du commit du dépôt ;
- la version de Python ;
- l’OS.

## L’archive contient des artefacts locaux

On trouve :

```text
.pytest_cache/
__pycache__/
.vscode/
```

Ils ne sont pas graves techniquement, mais donnent un dépôt moins propre pour publication.

Ajouter un `.gitignore` et nettoyer l’archive.

## Les modules d’évaluation ne sont pas inclus dans le package

La configuration setuptools n’inclut que :

```toml
include = ["acm*"]
```

Les packages suivants ne sont donc pas distribués avec le package Python :

```text
adapters
harness
ports
scenarios
```

Cela peut être volontaire si PyPI ne doit distribuer que le noyau. Il faut toutefois alors fournir deux modes explicites :

- package `acm-core` ;
- dépôt expérimental complet clonable.

---

# 6. Gap analysis technique

## 6.1. État actuel

| Axe | Maturité estimée |
|---|---:|
| Métamodèle des ACI | 80 % |
| Séparation lifecycle/quality/assurance | 90 % |
| Propagation déterministe | 80 % |
| Assurance composite | 80 % |
| Machines à états | 75 % |
| Baselines et digests | 70 % |
| Validité structurelle | 70 % |
| Runtime normalisé | 70 % |
| Agents dynamiques et permissions | 70 % |
| Drift et conformité | 55 % |
| Adaptateurs framework | 45 % |
| Import automatique de systèmes natifs | 20 % |
| Reporting expérimental | 55 % |
| Reproductibilité complète | 55 % |
| Performance | 35 % |
| Stockage append-only / audit trail | 25 % |
| Change control SCM | 15 % |
| Deployment state / observed state | 10 % |

## 6.2. Gaps bloquants avant gel technique v0.1

Je considère les points suivants comme prioritaires :

1. **Corriger S02** : référence obligatoire absente → blocage d’éligibilité.
2. **Corriger S20** : override comportemental interdit → blocage.
3. **Générer un résultat structuré pour les 27 scénarios.**
4. **Régénérer automatiquement le rapport Markdown.**
5. **Exécuter réellement la matrice LangGraph/CrewAI et conserver les logs.**
6. **Ajouter PyYAML et verrouiller les versions.**
7. **Formaliser le modèle de drift/conformité dans le noyau.**
8. **Qualifier précisément l’immuabilité de la baseline.**

## 6.3. Gaps non bloquants pour un premier preprint

Ces éléments peuvent raisonnablement être présentés comme limites ou travaux futurs :

- optimisation pour plusieurs milliers d’ACI ;
- stockage distribué ;
- signatures cryptographiques ;
- registre distant ;
- contrôleur de réconciliation ;
- intégration GitOps ;
- monitoring live ;
- import complet de graphes complexes ;
- support de plus de deux frameworks ;
- évaluations sémantiques avec LLM ;
- change approval organisationnel complet.

---

# 7. Gap analysis pour l’article

Le projet est parti d’un besoin de versionnement de prompts, puis a été repositionné vers un modèle de gestion de configuration agentique. Cette évolution est cohérente avec la roadmap initiale, qui identifiait déjà comme contribution centrale les objets versionnés, les baselines, la propagation, les invariants et le prototype. fileciteturn0file0L1-L87

## 7.1. Contributions désormais soutenables

Avec quelques corrections de formulation, l’article peut défendre :

### C1 — Métamodèle de configuration composite

Un système agentique est représenté comme un graphe d’ACI versionnés et reliés.

### C2 — Modèle d’état multidimensionnel

ACM sépare :

```text
lifecycle
quality
assurance
impact
eligibility
```

et distingue états déclarés et calculés.

### C3 — Propagation restrictive

Les problèmes de dépendances dégradent l’impact, l’assurance ou l’éligibilité sans réécrire abusivement l’état intrinsèque des composites.

### C4 — Assurance fondée sur des preuves révisionnées

Les preuves ciblent des révisions et digests exacts et sont invalidées lorsqu’une dépendance snapshotée change.

### C5 — Gestion des configurations runtime dynamiques

Les agents créés à l’exécution sont reliés à une définition, une factory, une configuration résolue, des permissions et un digest.

### C6 — Normalisation framework-independent

Un contrat runtime commun peut recevoir des signaux provenant d’adaptateurs LangGraph et CrewAI sur les cas minimaux testés.

### C7 — Prototype et scénarios

Le modèle est instancié par une implémentation Python et évalué à travers 27 scénarios conceptuels, dont 11 fixtures déclaratives.

---

## 7.2. Contributions qui ne sont pas encore suffisamment démontrées

### Portabilité générale

Deux adaptateurs minimaux ne suffisent pas à prouver une portabilité universelle.

### Utilité opérationnelle comparative

Les scénarios montrent que les fonctions ACM sont réalisables. Ils ne mesurent pas encore :

```text
sans ACM
versus
avec ACM
```

sur une tâche d’investigation, de rollback ou d’analyse d’impact.

### Supériorité sur les outils existants

Le prototype ne compare pas expérimentalement ACM à LangSmith, MLflow, W&B ou AgentOps. La différence reste principalement conceptuelle et documentaire.

### Scalabilité

Le rapport montre surtout que l’implémentation naïve convient à quelques centaines d’ACI. Il ne démontre pas une scalabilité industrielle.

### Reproductibilité comportementale

Le système reproduit la configuration et le replay structurel, pas les sorties probabilistes. Cette limite doit être explicite.

### Gestion complète de configuration

Le prototype couvre fortement :

- identification ;
- baselines ;
- status accounting partiel ;
- auditabilité ;
- runtime provenance.

Il couvre encore peu :

- change request ;
- approbation organisationnelle ;
- build/release pipeline complet ;
- configuration audit externe ;
- deployment reconciliation.

Il faut présenter ACM v0.1 comme un **core model**, non comme une plateforme SCM complète.

---

# 8. Évaluation de la maturité de l’article

| Partie de l’article | État estimé |
|---|---:|
| Motivation et problème | 85 % |
| État de l’art conceptuel | 75 % |
| Research gap | 70 % |
| Définitions et métamodèle | 85 % |
| Formalisation des états | 90 % |
| Invariants | 85 % |
| Architecture de référence | 80 % |
| Implémentation | 80 % |
| Protocole d’évaluation | 75 % |
| Résultats expérimentaux | 55 % |
| Comparaison inter-framework | 40 % |
| Discussion des limites | 75 % |
| Reproductibility package | 50 % |
| Validation bibliographique finale | à vérifier séparément |

### Estimation consolidée

- **Partie conceptuelle et formelle : environ 80–85 %.**
- **Partie technique du prototype : environ 70–75 %.**
- **Partie expérimentale publiable : environ 50–60 %.**
- **Article complet prêt pour arXiv : environ 65–70 %.**

Le projet n’a plus besoin d’une extension conceptuelle majeure avant le premier article. Il a surtout besoin d’un **gel normatif**, d’une consolidation de l’expérimentation et d’un reporting totalement reproductible.

---

# 9. Plan d’action recommandé

## P0 — Avant rédaction finale des résultats

1. Corriger ou accepter normativement S02 et S20.
2. Remplacer les statuts binaires par `pass`, `pass_with_deviation`, `skipped`, `fail`.
3. Produire un JSON consolidé couvrant S01–S27.
4. Générer le rapport Markdown depuis ce JSON.
5. Installer LangGraph, CrewAI et Hypothesis dans une CI reproductible.
6. Corriger les chiffres 220/3.
7. Ajouter PyYAML aux dépendances d’évaluation.
8. Ajouter versions exactes, environnement et commit aux rapports.

## P1 — Pour renforcer significativement l’article

1. Ajouter deux workflows non triviaux par framework :
   - branche conditionnelle LangGraph ;
   - crew multi-agent avec dépendances de tâches.
2. Mesurer :
   - éléments extraits automatiquement ;
   - annotations manuelles ;
   - pertes d’information ;
   - lignes de code par adaptateur.
3. Ajouter un benchmark reproductible sur :
   - 100 ;
   - 500 ;
   - 1 000 ;
   - éventuellement 5 000 ACI.
4. Indexer les relations pour corriger la complexité.
5. Ajouter un scénario comparatif d’analyse d’impact :
   - investigation manuelle ;
   - investigation via ACM.

## P2 — Après le premier preprint

- registre persistant append-only ;
- signatures et attestations ;
- deployment state ;
- change-control workflow ;
- contrôleur de drift ;
- adaptateur OpenAI Agents SDK ou Google ADK ;
- étude utilisateur ou industrielle.

---

# Avis final

**Le noyau scientifique est suffisamment solide pour poursuivre directement vers l’article.** Il n’est plus nécessaire d’élargir le métamodèle avant publication.

La priorité doit maintenant passer de :

```text
ajouter de nouveaux concepts
```

à :

```text
rendre chaque affirmation expérimentalement traçable
```

Après correction des divergences du rapport, exécution attestée des dépendances optionnelles et consolidation machine-readable des 27 scénarios, le dépôt pourra raisonnablement servir de **reference implementation et reproducibility package** pour un premier article arXiv.

Dans son état actuel, je le qualifierais de :

> **prototype technique convaincant et modèle formel avancé, avec une validation fonctionnelle étendue, mais une preuve expérimentale consolidée encore incomplète.**