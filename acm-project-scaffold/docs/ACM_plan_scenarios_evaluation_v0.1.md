# ACM — Plan de scénarios pour l’évaluation du modèle

**Document de travail**  
**Version :** 0.1  
**Objet :** définir les scénarios expérimentaux nécessaires pour évaluer ACM en vue de l’article arXiv  
**Périmètre recommandé :** noyau ACM indépendant du framework, puis intégrations LangGraph et CrewAI

---

## 1. Objectif de l’évaluation

L’évaluation ne doit pas seulement démontrer que l’implémentation Python fonctionne. Elle doit permettre d’étayer les affirmations scientifiques suivantes :

1. ACM représente un système agentique comme une configuration composite composée d’objets identifiables et versionnés.
2. Une baseline ACM permet de figer une configuration exacte et vérifiable.
3. Les changements de composants peuvent être propagés sous forme d’impact, de perte d’assurance ou de blocage d’éligibilité sans modifier abusivement les états intrinsèques.
4. Les mutations runtime peuvent être enregistrées puis rejouées de manière déterministe.
5. ACM distingue les mutations autorisées du drift non conforme.
6. Une même sémantique ACM peut être appliquée à des frameworks agentiques différents.
7. ACM apporte une traçabilité et une gestion de configuration que les frameworks d’orchestration ne fournissent pas seuls.

L’évaluation doit donc couvrir quatre axes :

- **correction normative** ;
- **reproductibilité** ;
- **indépendance vis-à-vis du framework** ;
- **utilité opérationnelle**.

---

# 2. Périmètre des frameworks

## 2.1. Recommandation

Pour le premier article, il est recommandé de se limiter à :

- **LangGraph** ;
- **CrewAI**.

Tous les scénarios normatifs doivent néanmoins être exécutables directement sur le noyau ACM, sans dépendre d’un framework.

La stratégie recommandée est donc :

```text
Scénarios normatifs
        ↓
ACM Core indépendant
        ↓
Sous-ensemble représentatif
        ├── Adaptateur LangGraph
        └── Adaptateur CrewAI
```

## 2.2. Pourquoi LangGraph ?

LangGraph est pertinent parce qu’il expose :

- une topologie explicite ;
- des nœuds ;
- des arêtes ;
- des transitions conditionnelles ;
- un état partagé ;
- des checkpoints et mécanismes de reprise.

Il permet de tester facilement :

- l’extraction d’un graphe de configuration ;
- la correspondance entre graphe déclaré et graphe exécuté ;
- le replay ;
- les changements de chemins d’exécution ;
- les différences entre état runtime et version de configuration.

## 2.3. Pourquoi CrewAI ?

CrewAI apporte un contrepoint utile :

- agents, tâches, crews et flows sont distincts ;
- une partie de la configuration peut être déclarée en YAML ;
- une autre partie demeure dans le code Python ;
- les dépendances entre tâches peuvent être explicites ou dérivées de l’orchestration ;
- la persistance des flows est distincte de la gestion de configuration.

CrewAI permet donc de vérifier qu’ACM ne dépend pas implicitement du métamodèle de LangGraph.

## 2.4. Frameworks différés

Les frameworks suivants peuvent être ajoutés dans une extension ou dans les travaux futurs :

- OpenAI Agents SDK ;
- Google ADK ;
- Microsoft Agent Framework ;
- Strands Agents ;
- AutoGen ;
- Semantic Kernel ;
- LlamaIndex Workflows ;
- Haystack Agents.

Pour le premier article, leur ajout augmenterait fortement l’effort sans améliorer proportionnellement la démonstration. Un troisième framework ne devient utile que si LangGraph et CrewAI révèlent une dépendance structurelle non résolue.

---

# 3. Organisation des scénarios

Les scénarios sont répartis en cinq groupes.

| Groupe | Finalité |
|---|---|
| A | Validation de la configuration et de la baseline |
| B | Propagation de qualité, assurance, impact et éligibilité |
| C | Runtime, replay et drift |
| D | Agents dynamiques et permissions |
| E | Portabilité et comparaison entre frameworks |

Les scénarios **P0** sont nécessaires pour l’article.  
Les scénarios **P1** renforcent significativement la validation.  
Les scénarios **P2** peuvent être reportés en annexe ou dans une version ultérieure.

---

# 4. Métriques communes

Chaque scénario doit produire un résultat structuré contenant au minimum :

```json
{
  "scenario_id": "ACM-S01",
  "framework": "core | langgraph | crewai",
  "configuration_digest": "sha256:...",
  "evidence_digest": "sha256:...",
  "expected_status": {},
  "observed_status": {},
  "invariants_checked": [],
  "runtime_event_count": 0,
  "propagation_iterations": 0,
  "converged": true,
  "execution_time_ms": 0,
  "result": "pass | fail"
}
```

## 4.1. Métriques de correction

- conformité du résultat à l’oracle attendu ;
- nombre d’invariants satisfaits ;
- nombre d’invariants violés correctement détectés ;
- absence de faux `assessed` ;
- absence de faux `eligible` ;
- exactitude de la classification du drift.

## 4.2. Métriques de reproductibilité

- stabilité du digest ;
- stabilité du résultat après permutation des entrées ;
- déterminisme du replay ;
- déterminisme de la propagation ;
- convergence ;
- nombre d’itérations jusqu’au point fixe.

## 4.3. Métriques de portabilité

- proportion des concepts du framework mappés automatiquement vers des ACI ;
- nombre de champs nécessitant une annotation manuelle ;
- perte d’information lors de l’import ;
- équivalence des états ACM produits pour deux implémentations fonctionnellement comparables ;
- volume de code spécifique à chaque adaptateur.

## 4.4. Métriques d’utilité

- nombre d’objets impactés correctement identifiés après un changement ;
- nombre d’évaluations à relancer identifiées ;
- capacité à expliquer un blocage par une chaîne de raisons ;
- capacité à reconstruire la configuration exacte d’une exécution ;
- capacité à distinguer mutation attendue et drift.

---

# 5. Groupe A — Configuration et baseline

## ACM-S01 — Configuration nominale et promotion d’une baseline

**Priorité :** P0  
**Frameworks :** Core, LangGraph, CrewAI

### Objectif

Démontrer qu’une configuration valide composée d’un système, d’un workflow, d’un agent, d’un prompt, d’un modèle et d’un outil peut être résolue, validée et figée dans une baseline.

### Configuration

```text
System S1
└── Workflow W1
    └── Agent A1
        ├── Prompt P1
        ├── Tool T1
        └── Model M1
```

Tous les ACI sont :

```text
lifecycle_state = validated
quality_state = ok
effective_assurance = assessed
eligibility_state = eligible
```

### Actions

1. Charger la configuration.
2. Résoudre toutes les références.
3. Calculer les états effectifs.
4. Créer une baseline candidate.
5. Vérifier le digest.
6. Promouvoir la baseline en `released`.

### Résultats attendus

- toutes les références sont exactes ;
- la propagation converge ;
- tous les objets sont éligibles ;
- la baseline est créée ;
- le digest recalculé correspond au digest stocké ;
- la baseline peut passer à `released`.

### Propriétés évaluées

- représentation composite ;
- exactitude des références ;
- promotion atomique ;
- déterminisme du digest.

---

## ACM-S02 — Référence obligatoire manquante

**Priorité :** P0  
**Frameworks :** Core ; adaptation facultative LangGraph/CrewAI

### Objectif

Vérifier qu’une configuration incomplète n’est pas silencieusement acceptée.

### Modification

`A1` référence un `ModelProfile M_missing` absent du graphe.

### Résultats attendus

```text
configuration_valid = false
A1.eligibility_state = blocked
baseline_creation = forbidden
```

Le rapport doit identifier :

- la référence manquante ;
- le chemin exact ;
- la relation concernée ;
- le code d’erreur stable.

### Propriétés évaluées

- complétude structurelle ;
- prévention des faux positifs ;
- explicabilité.

---

## ACM-S03 — Identité exacte : revision_id correct, digest incorrect

**Priorité :** P0  
**Frameworks :** Core

### Objectif

Démontrer qu’une référence ou une preuve ne peut pas être acceptée sur la seule base du `revision_id`.

### Modification

Une preuve cible :

```text
revision_id = R1
digest = digest_incorrect
```

alors que l’ACI possède :

```text
revision_id = R1
digest = digest_correct
```

### Résultats attendus

```text
evidence_applicability = inapplicable
effective_assurance != assessed
eligibility_state = blocked
```

### Propriétés évaluées

- identité matérielle ;
- intégrité des preuves ;
- invariant de ciblage exact.

---

## ACM-S04 — Immutabilité d’une baseline released

**Priorité :** P0  
**Frameworks :** Core

### Objectif

Vérifier qu’une baseline released ne peut pas être modifiée en place.

### Actions

1. Créer et publier une baseline.
2. Modifier un composant, une relation ou une métadonnée couverte par le digest.
3. Recalculer le digest.

### Résultats attendus

- la mutation directe est refusée ou détectée ;
- le digest ne correspond plus ;
- une nouvelle baseline est exigée ;
- la baseline historique reste consultable et intacte.

### Propriétés évaluées

- immutabilité logique ;
- auditabilité ;
- versionnement des changements.

---

# 6. Groupe B — Propagation et assurance

## ACM-S05 — Dépendance bloquante avec qualité NOK

**Priorité :** P0  
**Frameworks :** Core, LangGraph, CrewAI

### Objectif

Vérifier la distinction entre qualité intrinsèque et qualité effective.

### Modification

```text
T1.quality_state = nok
relation A1 uses_tool T1:
    required = true
    propagation_policy = blocking
```

### Résultats attendus

```text
T1.effective_quality = nok
A1.declared_quality reste inchangée
A1.effective_quality = nok
A1.eligibility_state = blocked
W1.eligibility_state = blocked
baseline_release = forbidden
```

Le lifecycle de `A1` et `W1` ne doit pas être copié depuis celui de `T1`.

### Propriétés évaluées

- propagation restrictive ;
- séparation état déclaré / état calculé ;
- blocage de promotion.

---

## ACM-S06 — Dépendance non bloquante avec qualité NOK

**Priorité :** P1  
**Frameworks :** Core

### Objectif

Vérifier la sémantique des relations `warning`.

### Modification

```text
relation A1 uses_tool T1:
    required = false
    propagation_policy = warning
T1.effective_quality = nok
```

### Résultats attendus

```text
A1.effective_quality != nok du seul fait de T1
A1.eligibility_state = warning
```

Une raison structurée doit référencer `T1` et la relation.

### Propriétés évaluées

- propagation par type de relation ;
- gestion des dépendances optionnelles ;
- explicabilité.

---

## ACM-S07 — Nouvelle révision de prompt et invalidation des preuves

**Priorité :** P0  
**Frameworks :** Core, LangGraph, CrewAI

### Objectif

Démontrer la propagation d’impact et la péremption des preuves après modification d’une dépendance.

### Situation initiale

```text
Agent A1@R1 uses Prompt P1@R1
Evidence E1 couvre A1@R1 avec snapshot P1@R1
```

### Modification

```text
P1@R2 replaces P1@R1
A1@R2 uses P1@R2
```

### Résultats attendus

Pour `A1@R2` :

```text
lifecycle_state = draft
quality_state = unknown
effective_assurance = unassessed
eligibility_state = blocked
```

Pour `E1` :

```text
applicable à A1@R1
non applicable à A1@R2
```

Si la révision d’agent reste identique mais que son snapshot de dépendances diverge :

```text
evidence_applicability = stale
```

### Propriétés évaluées

- versionnement fin ;
- lineage ;
- staleness ;
- absence de réutilisation implicite des preuves.

---

## ACM-S08 — Couverture d’assurance répartie sur plusieurs preuves

**Priorité :** P0  
**Frameworks :** Core

### Objectif

Vérifier que plusieurs preuves peuvent couvrir conjointement les dimensions exigées.

### Politique

```text
required_assurance_dimensions:
    - functional
    - security
    - robustness
```

### Preuves

```text
E1 couvre functional
E2 couvre security
E3 couvre robustness
```

### Résultats attendus

Après `E1` :

```text
effective_assurance = partially_assessed
```

Après `E1 + E2` :

```text
effective_assurance = partially_assessed
```

Après `E1 + E2 + E3` :

```text
effective_assurance = assessed
```

Le retrait ou l’expiration de `E2` ramène l’état à :

```text
partially_assessed
```

### Propriétés évaluées

- modèle de couverture ;
- recomputation ;
- séparation entre couverture et résultat des tests.

---

## ACM-S09 — Preuve complète mais résultat bloquant en échec

**Priorité :** P0  
**Frameworks :** Core

### Objectif

Démontrer formellement que `assessed` ne signifie pas `passed`.

### Preuve

Une preuve couvre toutes les dimensions mais contient :

```text
result = fail
blocking = true
```

### Résultats attendus

```text
effective_assurance = assessed
effective_quality = nok
eligibility_state = blocked
```

### Propriétés évaluées

- indépendance qualité / assurance ;
- exactitude du contrat sémantique.

---

## ACM-S10 — Modes direct_only, aggregate_only et hybrid

**Priorité :** P0  
**Frameworks :** Core

### Objectif

Vérifier les trois politiques d’assurance des compositions.

### Cas A — `direct_only`

- preuves directes complètes ;
- dépendances non évaluées.

Résultat :

```text
effective_assurance = assessed
```

### Cas B — `aggregate_only`

- aucune preuve directe ;
- toutes les dépendances d’assurance sont assessed.

Résultat :

```text
effective_assurance = assessed
```

### Cas C — `hybrid`

- preuves directes complètes ;
- une dépendance non assessed.

Résultat :

```text
effective_assurance != assessed
```

### Cas D — anti-vacuité

```text
composition_mode = aggregate_only
assurance_dependency_count = 0
allow_vacuous_assessment = false
```

Résultat :

```text
effective_assurance = unassessed
```

### Propriétés évaluées

- règles de composition ;
- absence d’assessment par vacuité ;
- comportement déterministe des politiques.

---

## ACM-S11 — Politique absente versus politique explicitement vide

**Priorité :** P0  
**Frameworks :** Core

### Objectif

Vérifier que les deux situations restent distinguables.

### Cas A

```text
assurance_policy = null
```

Résultat :

```text
effective_assurance = unassessed
```

### Cas B

```text
assurance_policy présent
required_assurance_dimensions = []
```

Le résultat dépend de la règle normative explicite retenue, mais il doit être différent du cas A et visible dans le rapport.

### Propriétés évaluées

- fidélité du contrat ;
- absence de valeurs par défaut ambiguës ;
- sérialisation.

---

# 7. Groupe C — Runtime, replay et drift

## ACM-S12 — Replay nominal déterministe

**Priorité :** P0  
**Frameworks :** Core, LangGraph, CrewAI

### Objectif

Vérifier que la même baseline et le même journal produisent le même graphe runtime.

### Journal

```text
node.instantiated
state.changed(created → ready)
state.changed(ready → running)
tool.invoked
tool.completed
state.changed(running → completed)
node.terminated
```

### Actions

1. Rejouer le journal une première fois.
2. Sérialiser le graphe obtenu.
3. Rejouer le même journal.
4. Comparer les graphes et digests.

### Résultats attendus

```text
runtime_graph_1 = runtime_graph_2
runtime_digest_1 = runtime_digest_2
drift = none ou expected_runtime
```

### Propriétés évaluées

- replay ;
- déterminisme ;
- reconstruction runtime.

---

## ACM-S13 — Ordre d’événements invalide

**Priorité :** P0  
**Frameworks :** Core

### Objectif

Vérifier que le moteur détecte une séquence incohérente.

### Anomalies testées

- événement dupliqué ;
- terminaison avant instanciation ;
- transition `completed → running` ;
- rupture de numéro de séquence ;
- suppression d’une relation inexistante.

### Résultats attendus

- événement rejeté ou journal déclaré invalide ;
- code d’erreur explicite ;
- aucun état silencieusement corrigé ;
- graphe partiel clairement signalé comme non fiable.

### Propriétés évaluées

- intégrité du journal ;
- machine à états runtime ;
- auditabilité.

---

## ACM-S14 — Mutation runtime autorisée

**Priorité :** P0  
**Frameworks :** Core, LangGraph ou CrewAI selon le mécanisme choisi

### Objectif

Distinguer une mutation autorisée d’un drift.

### Situation

Une factory validée crée une instance conforme :

- template autorisé ;
- override autorisé ;
- permissions sous le plafond ;
- provenance complète.

### Résultats attendus

```text
classification = declared_extension
drift_severity = none
runtime_graph reconstructible = true
```

La baseline ne doit pas être modifiée.

### Propriétés évaluées

- distinction baseline/runtime ;
- mutation déclarée ;
- provenance.

---

## ACM-S15 — Mutation runtime non déclarée

**Priorité :** P0  
**Frameworks :** Core, puis un framework

### Objectif

Détecter une instance inconnue ne pouvant être reliée à aucune définition ni factory.

### Résultats attendus

```text
classification = untraceable_instance
severity = critical
eligibility_state = blocked
```

Le replay peut techniquement conserver l’événement, mais le rapport doit indiquer que la provenance est insuffisante.

### Propriétés évaluées

- drift ;
- traçabilité ;
- séparation observation/conformité.

---

## ACM-S16 — Drift de configuration d’un prompt au runtime

**Priorité :** P1  
**Frameworks :** LangGraph, CrewAI

### Objectif

Détecter que le prompt réellement utilisé ne correspond pas à la baseline.

### Situation

La baseline référence :

```text
Prompt P1@R1
digest = D1
```

L’exécution utilise un texte ou template produisant :

```text
digest = D2
```

### Résultats attendus

```text
classification = configuration_drift
affected_item = P1
severity = high ou critical
runtime_execution remains observable
release conformity = false
```

### Propriétés évaluées

- configuration observée ;
- comparaison baseline/runtime ;
- utilité de l’identité par digest.

---

## ACM-S17 — Baseline retirée après exécution historique

**Priorité :** P1  
**Frameworks :** Core

### Objectif

Vérifier que le retrait d’une baseline ne modifie pas rétroactivement l’historique.

### Actions

1. Exécuter et enregistrer un run avec `B1`.
2. Passer `B1` à `withdrawn`.
3. Rejouer le run historique.
4. Tenter un nouveau run avec `B1`.

### Résultats attendus

- le run historique reste reconstructible ;
- son lien avec `B1` est conservé ;
- une nouvelle exécution est bloquée par défaut ;
- le retrait n’altère ni le journal ni les digests historiques.

### Propriétés évaluées

- temporalité ;
- auditabilité ;
- distinction historique/opérationnel.

---

# 8. Groupe D — Agents dynamiques et permissions

## ACM-S18 — Agent dynamique conforme

**Priorité :** P0  
**Frameworks :** Core ; intégration CrewAI ou LangGraph selon le démonstrateur

### Objectif

Évaluer la gestion d’une instance générée à l’exécution à partir d’une factory connue.

### Configuration

```text
Factory F1 = validated
Template AT = validated
Creator AC = validated
```

La factory autorise :

- un changement de spécialisation ;
- un prompt contextuel ;
- un ensemble limité d’outils ;
- une durée de vie limitée au run.

### Résultats attendus à la création

```text
promotion_state = ephemeral
configuration_digest présent
source factory présente
source template présente
effective_assurance = partially_assessed ou valeur définie par la politique
runtime_eligibility = warning ou eligible selon les contrôles
```

Après contrôles runtime réussis :

```text
quality scoped to execution = ok
assurance scoped to execution = assessed
```

L’instance ne devient jamais automatiquement un ACI permanent.

### Propriétés évaluées

- définition/instance ;
- provenance générative ;
- portée des preuves ;
- lifecycle de promotion.

---

## ACM-S19 — Escalade de permissions refusée

**Priorité :** P0  
**Frameworks :** Core, puis framework

### Objectif

Vérifier l’invariant :

```text
P_instance ⊆ P_creator ∩ P_factory ∩ P_environment
```

### Modification

L’instance demande une capacité absente du plafond :

```text
filesystem:write
```

### Résultats attendus

```text
instance_creation = rejected ou quarantined
permission_drift = critical
eligibility_state = blocked
```

Le runtime event doit conserver la tentative et la décision.

### Propriétés évaluées

- non-escalade ;
- gouvernance des mutations ;
- auditabilité.

---

## ACM-S20 — Override comportemental interdit

**Priorité :** P1  
**Frameworks :** Core

### Objectif

Vérifier qu’un agent dynamique ne peut modifier que les champs autorisés.

### Situation

La factory autorise :

```text
purpose
specialization
```

mais l’instance modifie :

```text
tool_refs
model_ref
policy_refs
```

### Résultats attendus

```text
classification = forbidden_override
eligibility_state = blocked
effective_assurance = unassessed
```

### Propriétés évaluées

- contraintes de factory ;
- stabilité des configurations dérivées ;
- contrôle des capacités.

---

## ACM-S21 — Promotion d’un agent runtime

**Priorité :** P1  
**Frameworks :** Core

### Objectif

Vérifier qu’une instance runtime ne peut pas devenir directement une révision `validated`.

### Trajectoire attendue

```text
ephemeral
→ retained
→ candidate
→ nouvelle ACI revision draft/candidate
→ validation
→ registered/validated
```

### Résultats attendus

Une tentative :

```text
ephemeral → validated
```

doit être rejetée.

La promotion correcte doit produire :

- un nouvel `revision_id` ;
- un digest ;
- une provenance ;
- des preuves propres ;
- une approbation.

### Propriétés évaluées

- promotion contrôlée ;
- séparation runtime/configuration ;
- invariant de non-promotion directe.

---

# 9. Groupe E — Portabilité entre frameworks

## ACM-S22 — Même système logique en LangGraph et CrewAI

**Priorité :** P0  
**Frameworks :** LangGraph et CrewAI

### Objectif

Évaluer l’indépendance du métamodèle ACM.

### Système logique commun

```text
Router
├── Researcher
└── Writer
```

Les deux implémentations utilisent :

- les mêmes rôles ;
- les mêmes prompts ;
- les mêmes outils simulés ;
- les mêmes politiques ;
- une orchestration fonctionnellement équivalente.

### Actions

1. Construire l’implémentation LangGraph.
2. Construire l’implémentation CrewAI.
3. Importer chaque configuration dans ACM.
4. Comparer les ACI et relations normalisés.
5. Exécuter un scénario nominal.
6. Comparer les rapports ACM.

### Résultats attendus

Les objets spécifiques au framework peuvent différer, mais les concepts communs doivent produire une projection équivalente :

- mêmes agents logiques ;
- mêmes dépendances critiques ;
- mêmes prompts et outils ;
- mêmes décisions d’éligibilité ;
- mêmes effets d’une modification de prompt.

### Métriques

- taux de couverture automatique ;
- champs manuels ;
- nombre de pertes sémantiques ;
- taille de chaque adaptateur ;
- équivalence des états calculés.

### Propriétés évaluées

- framework independence ;
- généralité du métamodèle ;
- faisabilité des adaptateurs.

---

## ACM-S23 — Topologie explicite versus configuration distribuée

**Priorité :** P1  
**Frameworks :** LangGraph et CrewAI

### Objectif

Comparer la capacité d’ACM à extraire une configuration lorsque la topologie est explicite ou répartie entre code et YAML.

### LangGraph

La topologie est principalement définie par :

- nœuds ;
- arêtes ;
- conditions.

### CrewAI

La configuration peut être répartie entre :

- `agents.yaml` ;
- `tasks.yaml` ;
- code du Crew ;
- code du Flow ;
- outils Python.

### Résultats attendus

Le rapport doit identifier :

- les éléments extraits automatiquement ;
- les éléments nécessitant des annotations ;
- les informations impossibles à résoudre statiquement ;
- les hypothèses de l’adaptateur.

### Propriétés évaluées

- limites d’import ;
- transparence ;
- applicabilité réaliste.

---

## ACM-S24 — Équivalence des événements runtime

**Priorité :** P1  
**Frameworks :** LangGraph et CrewAI

### Objectif

Vérifier que des événements natifs différents peuvent être projetés vers un vocabulaire runtime ACM commun.

### Événements communs recherchés

```text
node.instantiated
state.changed
agent.invoked
tool.invoked
tool.completed
handoff.created
node.completed
node.terminated
```

### Résultats attendus

- chaque framework produit un journal ACM valide ;
- le replay fonctionne ;
- les événements non mappables sont conservés comme extensions ;
- aucune information critique n’est silencieusement supprimée.

### Propriétés évaluées

- normalisation runtime ;
- extensibilité ;
- interopérabilité.

---

# 10. Tests transverses de robustesse

## ACM-S25 — Invariance à l’ordre des entrées

**Priorité :** P0  
**Frameworks :** Core

### Objectif

Vérifier que l’ordre des listes d’ACI, relations et preuves ne change pas le résultat.

### Résultats attendus

Pour toutes les permutations testées :

```text
computed_status identiques
report_digest identique
convergence identique
```

Lorsque l’ordre est sémantiquement significatif, notamment pour les événements runtime, il doit être explicitement préservé.

---

## ACM-S26 — Cycles de dépendances

**Priorité :** P1  
**Frameworks :** Core

### Objectif

Vérifier la convergence du moteur en présence d’un cycle autorisé.

### Configuration

```text
A depends_on B
B depends_on A
```

### Cas

1. tous les éléments sont assessed et ok ;
2. un élément est unassessed ;
3. un élément est nok.

### Résultats attendus

- calcul convergent ;
- états conformes à la politique ;
- nombre d’itérations enregistré ;
- absence de boucle infinie ;
- erreur explicite en cas de non-convergence artificiellement provoquée.

---

## ACM-S27 — Volume et passage à l’échelle local

**Priorité :** P2  
**Frameworks :** Core

### Objectif

Montrer que le noyau reste utilisable sur une machine CPU standard.

### Tailles proposées

```text
100 ACI / 300 relations
1 000 ACI / 3 000 relations
5 000 ACI / 15 000 relations
```

### Mesures

- temps de chargement ;
- temps de validation ;
- temps de propagation ;
- temps de replay ;
- mémoire ;
- nombre d’itérations.

### Résultat attendu

Il ne s’agit pas de démontrer des performances industrielles, mais une exécution reproductible et raisonnable pour le périmètre annoncé.

---

# 11. Matrice de couverture

| Scénario | Baseline | Identité | Propagation | Assurance | Runtime | Drift | Dynamique | Framework |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S01 | ✓ | ✓ | ✓ | ✓ |  |  |  | ✓ |
| S02 | ✓ | ✓ |  |  |  |  |  |  |
| S03 |  | ✓ |  | ✓ |  |  |  |  |
| S04 | ✓ | ✓ |  |  |  | ✓ |  |  |
| S05 | ✓ |  | ✓ |  |  |  |  | ✓ |
| S06 |  |  | ✓ |  |  |  |  |  |
| S07 | ✓ | ✓ | ✓ | ✓ |  |  |  | ✓ |
| S08 |  |  |  | ✓ |  |  |  |  |
| S09 |  |  | ✓ | ✓ |  |  |  |  |
| S10 |  |  | ✓ | ✓ |  |  |  |  |
| S11 |  |  |  | ✓ |  |  |  |  |
| S12 |  | ✓ |  |  | ✓ | ✓ |  | ✓ |
| S13 |  |  |  |  | ✓ | ✓ |  |  |
| S14 |  | ✓ |  | ✓ | ✓ | ✓ | ✓ | ✓ |
| S15 |  | ✓ |  |  | ✓ | ✓ | ✓ | ✓ |
| S16 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  | ✓ |
| S17 | ✓ | ✓ |  |  | ✓ |  |  |  |
| S18 |  | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| S19 |  |  | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| S20 |  | ✓ |  | ✓ | ✓ | ✓ | ✓ |  |
| S21 |  | ✓ |  | ✓ | ✓ |  | ✓ |  |
| S22 | ✓ | ✓ | ✓ | ✓ | ✓ |  |  | ✓ |
| S23 |  | ✓ |  |  |  |  |  | ✓ |
| S24 |  |  |  |  | ✓ | ✓ |  | ✓ |
| S25 | ✓ | ✓ | ✓ | ✓ |  |  |  |  |
| S26 |  |  | ✓ | ✓ |  |  |  |  |
| S27 | ✓ |  | ✓ |  | ✓ |  |  |  |

---

# 12. Sous-ensemble minimal pour l’article

Le corpus complet comporte 27 scénarios. Il n’est pas nécessaire de tous détailler dans le corps principal de l’article.

## 12.1. Scénarios principaux recommandés

### Cas d’étude 1 — Changement de prompt et staleness

Combiner :

- S01 ;
- S07 ;
- S08 ;
- S09.

Ce cas démontre :

- baseline ;
- versionnement ;
- snapshot de dépendances ;
- invalidation de preuve ;
- distinction qualité/assurance ;
- blocage de promotion.

### Cas d’étude 2 — Agent dynamique et drift

Combiner :

- S14 ;
- S15 ;
- S18 ;
- S19.

Ce cas démontre :

- mutation runtime ;
- provenance ;
- factory ;
- permissions ;
- declared extension versus drift critique.

### Cas d’étude 3 — Portabilité LangGraph/CrewAI

Combiner :

- S22 ;
- S23 ;
- S24.

Ce cas démontre :

- indépendance du framework ;
- limites de l’extraction ;
- vocabulaire runtime commun.

### Cas d’étude 4 — Dépendance NOK et propagation

Combiner :

- S05 ;
- S06 ;
- S10 ;
- S26.

Ce cas démontre :

- politiques de relation ;
- propagation restrictive ;
- assurance composite ;
- convergence.

## 12.2. Scénarios obligatoires en annexe ou dépôt

Tous les P0 doivent être exécutés automatiquement, même s’ils ne figurent pas dans le corps principal.

---

# 13. Design expérimental recommandé

## 13.1. Répétitions

Les scénarios déterministes n’ont pas besoin de nombreuses répétitions statistiques. Ils doivent être répétés pour vérifier :

- stabilité des digests ;
- stabilité du replay ;
- stabilité de la propagation ;
- indépendance à l’ordre des entrées.

Recommandation :

```text
10 répétitions par scénario déterministe
```

Les scénarios utilisant réellement un LLM doivent séparer :

- la configuration et les événements, qui doivent rester déterministes ;
- les sorties du modèle, qui peuvent varier.

La validation d’ACM ne doit pas dépendre du texte exact généré.

## 13.2. Outils simulés

Pour l’article initial, privilégier des outils locaux et déterministes :

- recherche dans une liste ou un petit corpus local ;
- calcul simple ;
- transformation de texte ;
- stockage en mémoire.

Cela permet d’évaluer ACM sans introduire les variations de services externes.

## 13.3. Modèles

Les scénarios de gestion de configuration peuvent utiliser :

- un faux modèle déterministe ;
- un stub ;
- ou un petit modèle/API uniquement pour illustrer l’intégration.

La contribution ne porte pas sur la qualité du LLM. Les résultats scientifiques doivent donc rester reproductibles sans appel externe lorsque cela est possible.

## 13.4. Oracles

Chaque scénario doit posséder un oracle explicite sous forme de fixture :

```yaml
expected:
  effective_quality: nok
  effective_assurance: assessed
  impact_state: stale
  eligibility_state: blocked
  drift_classification: configuration_drift
```

Les assertions ne doivent pas seulement vérifier un état global. Elles doivent aussi vérifier :

- les raisons ;
- les sources ;
- les relations ;
- les preuves applicables ou rejetées ;
- les invariants.

---

# 14. Critères de succès de l’évaluation

L’évaluation est considérée comme suffisante pour l’article si :

1. tous les scénarios P0 passent sur ACM Core ;
2. les scénarios S01, S05, S07, S12 et S22 passent avec LangGraph et CrewAI lorsque cela s’applique ;
3. le replay est déterministe ;
4. aucune preuve avec digest incorrect ou snapshot périmé n’est considérée applicable ;
5. les trois modes d’assurance produisent les résultats attendus ;
6. les mutations autorisées et non autorisées sont correctement distinguées ;
7. les résultats ne dépendent pas de l’ordre des entrées ;
8. le rapport explique chaque blocage ;
9. les deux adaptateurs projettent le même système logique vers une représentation ACM comparable ;
10. l’ensemble s’exécute sur CPU avec une procédure documentée.

---

# 15. Ordre d’implémentation recommandé

## Phase 1 — Verrouillage normatif

À implémenter en premier :

```text
S01, S02, S03, S05, S07, S08, S09, S10, S11, S25
```

## Phase 2 — Runtime

```text
S12, S13, S14, S15, S19
```

## Phase 3 — Adaptateurs

```text
S22, S23, S24
```

## Phase 4 — Renforcement

```text
S04, S06, S16, S17, S18, S20, S21, S26, S27
```

---

# 16. Conclusion

Pour le premier article, le choix **LangGraph + CrewAI** est suffisant et méthodologiquement pertinent, à condition que le noyau d’évaluation reste indépendant des frameworks.

LangGraph ne doit pas devenir le modèle implicite d’ACM. CrewAI sert précisément de test de généralité, car sa représentation de la configuration est moins directement graph-based et plus distribuée entre objets, YAML et code.

La démonstration la plus convaincante ne sera pas de multiplier les frameworks, mais de montrer que :

1. un même ensemble de règles ACM s’applique aux deux ;
2. les différences natives sont préservées ou explicitement signalées ;
3. les résultats de baseline, propagation, assurance, replay et drift restent comparables ;
4. ACM fournit des capacités transversales absentes des frameworks pris isolément.
