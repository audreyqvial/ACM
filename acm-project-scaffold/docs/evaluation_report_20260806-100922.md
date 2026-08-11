# ACM — Rapport d'évaluation consolidé (auto-généré)

**Généré le :** 2026-08-06 10:09:22 CEST  
**Python :** 3.13.14 — **Plateforme :** Linux x86_64  
**Frameworks disponibles :** langgraph=oui, crewai=oui, openai_agents=oui

> Ce rapport est généré automatiquement à partir des résultats de tests exécutés dans l'environnement courant. Le statut de chaque scénario est dérivé des tests, jamais codé en dur.

## 1. Synthèse

| Indicateur | Valeur |
|---|---|
| Scénarios couverts par au moins un test | 27 / 27 |
| — dont pass | 24 |
| — dont pass_with_deviation | 3 |
| — dont skipped | 0 |
| — dont fail | 0 |
| — dont not_executed | 0 |
| Tests passés | 295 |
| Tests échoués | 0 |
| Tests ignorés | 0 |
| Fixtures YAML mesurées | 11 |

## 2. Résultats par scénario

### Groupe A — Configuration et baseline

| ID | Priorité | Objet | Tests (P/F/S) | Statut |
|---|---|---|---|---|
| S01 | P0 | Configuration nominale, promotion | 5/0/0 | `pass` |
| S02 | P0 | Référence obligatoire manquante | 6/0/0 | `pass` |
| S03 | P0 | Identité exacte des preuves (digest) | 2/0/0 | `pass` |
| S04 | P0 | Immutabilité d'une baseline released | 13/0/0 | `pass` |

### Groupe B — Propagation et assurance

| ID | Priorité | Objet | Tests (P/F/S) | Statut |
|---|---|---|---|---|
| S05 | P0 | Dépendance bloquante NOK | 9/0/0 | `pass` |
| S06 | P1 | Dépendance non bloquante (warning) | 2/0/0 | `pass` |
| S07 | P0 | Nouvelle révision de prompt, invalidation | 9/0/0 | `pass` |
| S08 | P0 | Couverture d'assurance répartie | 6/0/0 | `pass` |
| S09 | P0 | Preuve complète, résultat en échec | 2/0/0 | `pass` |
| S10 | P0 | Modes direct/aggregate/hybrid | 7/0/0 | `pass` |
| S11 | P0 | Politique absente vs vide | 4/0/0 | `pass` |

### Groupe C — Runtime, replay et drift

| ID | Priorité | Objet | Tests (P/F/S) | Statut |
|---|---|---|---|---|
| S12 | P0 | Replay nominal déterministe | 4/0/0 | `pass` |
| S13 | P0 | Séquence runtime invalide | 2/0/0 | `pass` |
| S14 | P0 | Mutation runtime autorisée | 3/0/0 | `pass_with_deviation` |
| S15 | P0 | Mutation runtime non déclarée | 4/0/0 | `pass_with_deviation` |
| S16 | P1 | Drift de configuration d'un prompt | 4/0/0 | `pass_with_deviation` |
| S17 | P1 | Baseline retirée après run historique | 7/0/0 | `pass` |

### Groupe D — Agents dynamiques et permissions

| ID | Priorité | Objet | Tests (P/F/S) | Statut |
|---|---|---|---|---|
| S18 | P0 | Agent dynamique conforme | 14/0/0 | `pass` |
| S19 | P0 | Escalade de permissions refusée | 13/0/0 | `pass` |
| S20 | P1 | Override comportemental interdit | 5/0/0 | `pass` |
| S21 | P1 | Promotion d'un agent runtime | 5/0/0 | `pass` |

### Groupe E — Portabilité et robustesse

| ID | Priorité | Objet | Tests (P/F/S) | Statut |
|---|---|---|---|---|
| S22 | P0 | Même système en LangGraph et CrewAI | 2/0/0 | `pass` |
| S23 | P1 | Topologie explicite vs distribuée | 1/0/0 | `pass` |
| S24 | P1 | Équivalence des événements runtime | 2/0/0 | `pass` |
| S25 | P0 | Invariance à l'ordre des entrées | 3/0/0 | `pass` |
| S26 | P1 | Cycles de dépendances | 5/0/0 | `pass` |
| S27 | P2 | Volume et passage à l'échelle local | 3/0/0 | `pass` |

## 3. Déviations documentées (`pass_with_deviation`)

Ces scénarios passent tous leurs tests, mais leur comportement s'écarte de ce que le plan prescrivait à l'origine. La déviation est un choix assumé, non un défaut.

| Scénario | Justification |
|---|---|
| S14 | Détail de classification de drift (declared_extension) dérivé en couche de conformité, non porté nativement par l'énumération du moteur. |
| S15 | Classification untraceable_instance dérivée ; le moteur porte le drift_state discret (undeclared_instance) sans le détail explicatif. |
| S16 | Conformité de configuration (mismatch) évaluée comme résultat séparé, orthogonal au drift_state ; non promue en jugement de premier ordre. |

## 4. Métriques des fixtures de propagation (harness)

| Scénario | Priorité | Itérations | Temps (ms) | Convergence | Résultat |
|---|---|---|---|---|---|
| ACM-S01 | P0 | 3 | 0.73 | oui | pass |
| ACM-S02 | P0 | 2 | 0.22 | oui | pass |
| ACM-S03 | P0 | 2 | 0.22 | oui | pass |
| ACM-S05 | P0 | 3 | 0.28 | oui | pass |
| ACM-S06 | P1 | 3 | 0.20 | oui | pass |
| ACM-S07 | P0 | 2 | 0.16 | oui | pass |
| ACM-S08 | P0 | 2 | 0.12 | oui | pass |
| ACM-S09 | P0 | 2 | 0.10 | oui | pass |
| ACM-S10 | P0 | 2 | 0.16 | oui | pass |
| ACM-S11 | P0 | 2 | 0.09 | oui | pass |
| ACM-S13 | P0 | 1 | 0.04 | oui | pass |

## 5. Légende des statuts

| Statut | Signification |
|---|---|
| `pass` | Tous les tests du scénario passent, sans déviation |
| `pass_with_deviation` | Tests passent, mais le comportement s'écarte du plan (choix assumé — voir section 3) |
| `skipped` | Tous les tests du scénario ignorés (dépendance manquante) |
| `fail` | Au moins un test en échec |
| `not_executed` | Aucun test rattaché exécuté |

---

*Rapport généré automatiquement — 2026-08-06T10:09:22.015328+02:00*