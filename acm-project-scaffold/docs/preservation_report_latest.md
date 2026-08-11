# ACM — Information Preservation Report (auto-généré)

**Généré le :** 2026-08-11 01:30:20 CEST  
**Python :** 3.13.14 — **Plateforme :** Linux x86_64  
**Frameworks :** langgraph=oui, crewai=oui, openai_agents=oui

> Mesure la préservation d'information lors de l'extraction de workflows natifs non triviaux vers la représentation ACM. Chiffres dérivés de l'exécution des extracteurs, jamais codés en dur.

## Cadre

Pour chaque workflow natif F, on calcule E(F) (extraction) et on compare à une représentation golden manuelle sur le périmètre normatif d'ACM. Une propriété est `preserved` (reconstruite exactement), `approximated` (abstraction ACM conservée, ex. condition opaque) ou `unsupported` (aucun concept ACM correspondant).

## LangGraph

### Branche conditionnelle

| Métrique | Valeur |
|---|---|
| Couverture des nœuds | 100.0% |
| Couverture des relations | 100.0% |
| Couverture des branches | 100.0% |
| Entry point préservé | oui |
| Nœuds terminaux préservés | oui |
| Réf. agent–prompt | 100.0% |
| Réf. agent–outil | 100.0% |
| Éléments unresolved | 2 |
| Digest stable (extraction répétée) | oui |

**Périmètre normatif — statuts de préservation :**

- preserved : 10
- approximated : 1
- unsupported : 0

**Propriétés non intégralement préservées :**

| Propriété | Statut | Détail |
|---|---|---|
| conditional_branches | `approximated` | abstraction topologique conservée, sémantique opaque |

**Statuts d'extraction des nœuds :** extracted=3, declared_by_adapter=4, unresolved=0

## CrewAI — trois niveaux d'abstraction

CrewAI distingue plusieurs niveaux : un `Crew` (agents + tâches + process), un `Flow` (orchestration via start/router/listeners), et leur combinaison. On mesure les trois séparément pour ne pas confondre ce qui vient du Crew, du Flow, ou de leur fusion.

### Cas 1 — Crew-only (agents, tâches, contexte)

| Métrique | Valeur |
|---|---|
| Couverture des nœuds | 100.0% |
| Couverture des relations | 100.0% |
| Couverture des branches | 100.0% |
| Entry point préservé | oui |
| Nœuds terminaux préservés | oui |
| Réf. agent–prompt | 100.0% |
| Réf. agent–outil | 100.0% |
| Éléments unresolved | 0 |
| Digest stable (extraction répétée) | oui |

**Périmètre normatif — statuts de préservation :**

- preserved : 10
- approximated : 1
- unsupported : 0

**Propriétés non intégralement préservées :**

| Propriété | Statut | Détail |
|---|---|---|
| conditional_branches | `approximated` | abstraction topologique conservée, sémantique opaque |

**Statuts d'extraction des nœuds :** extracted=0, declared_by_adapter=3, unresolved=0

### Cas 2 — Flow-only (start, router, branches)

| Métrique | Valeur |
|---|---|
| Couverture des nœuds | 100.0% |
| Couverture des relations | 100.0% |
| Couverture des branches | 100.0% |
| Entry point préservé | oui |
| Nœuds terminaux préservés | oui |
| Réf. agent–prompt | 100.0% |
| Réf. agent–outil | 100.0% |
| Éléments unresolved | 2 |
| Digest stable (extraction répétée) | oui |

**Périmètre normatif — statuts de préservation :**

- preserved : 9
- approximated : 1
- unsupported : 1

**Propriétés non intégralement préservées :**

| Propriété | Statut | Détail |
|---|---|---|
| conditional_branches | `approximated` | abstraction topologique conservée, sémantique opaque |
| state_schema | `unsupported` | aucun élément extrait pour une propriété présente au golden |

**Statuts d'extraction des nœuds :** extracted=4, declared_by_adapter=2, unresolved=0

### Cas 3 — Flow+Crew (orchestration + tâches fusionnées)

| Métrique | Valeur |
|---|---|
| Couverture des nœuds | 100.0% |
| Couverture des relations | 100.0% |
| Couverture des branches | 100.0% |
| Entry point préservé | oui |
| Nœuds terminaux préservés | oui |
| Réf. agent–prompt | 100.0% |
| Réf. agent–outil | 100.0% |
| Éléments unresolved | 2 |
| Digest stable (extraction répétée) | oui |

**Périmètre normatif — statuts de préservation :**

- preserved : 9
- approximated : 1
- unsupported : 1

**Propriétés non intégralement préservées :**

| Propriété | Statut | Détail |
|---|---|---|
| conditional_branches | `approximated` | abstraction topologique conservée, sémantique opaque |
| state_schema | `unsupported` | aucun élément extrait pour une propriété présente au golden |

**Statuts d'extraction des nœuds :** extracted=4, declared_by_adapter=5, unresolved=0

### Lecture des cas Flow — extraction vs déclaration

Le Flow CrewAI illustre la frontière d'extractibilité, centrale pour l'article. Les nœuds et leurs rôles (start/router/listen) sont lus directement depuis `flow._methods` (4 nœud(s) `extracted`). En revanche, la topologie des arêtes n'est pas introspectable statiquement dans les versions récentes de CrewAI (elle est résolue à l'exécution) : les arêtes sont fournies par métadonnées (`declared_by_adapter`, 2 nœud(s) concerné(s)). Contrairement à LangGraph, dont la topologie est explicite et entièrement extraite, le Flow CrewAI relève partiellement de la déclaration d'adaptateur — une distinction que le métamodèle ACM rend explicite plutôt que de la masquer.

## OpenAI Agents SDK — deux niveaux d'abstraction

Le SDK OpenAI Agents exprime un système multi-agents comme un `Agent` racine portant des `handoffs` (délégations) et des `tools`. On mesure deux niveaux : un `Agent` isolé (mono-nœud) et le graphe complet obtenu par fermeture transitive des handoffs. À la différence du Flow CrewAI, la topologie de handoffs est directement lisible sur les objets — les arêtes sont donc extraites, pas déclarées.

### Cas 1 — Agent seul (mono-nœud, outils)

| Métrique | Valeur |
|---|---|
| Couverture des nœuds | 100.0% |
| Couverture des relations | 100.0% |
| Couverture des branches | 100.0% |
| Entry point préservé | oui |
| Nœuds terminaux préservés | oui |
| Réf. agent–prompt | 100.0% |
| Réf. agent–outil | 100.0% |
| Éléments unresolved | 0 |
| Digest stable (extraction répétée) | oui |

**Périmètre normatif — statuts de préservation :**

- preserved : 10
- approximated : 1
- unsupported : 0

**Propriétés non intégralement préservées :**

| Propriété | Statut | Détail |
|---|---|---|
| conditional_branches | `approximated` | abstraction topologique conservée, sémantique opaque |

**Statuts d'extraction des nœuds :** extracted=0, declared_by_adapter=1, unresolved=0

### Cas 2 — Agent + handoffs (graphe de délégation)

| Métrique | Valeur |
|---|---|
| Couverture des nœuds | 100.0% |
| Couverture des relations | 100.0% |
| Couverture des branches | 100.0% |
| Entry point préservé | oui |
| Nœuds terminaux préservés | oui |
| Réf. agent–prompt | 100.0% |
| Réf. agent–outil | 100.0% |
| Éléments unresolved | 0 |
| Digest stable (extraction répétée) | oui |

**Périmètre normatif — statuts de préservation :**

- preserved : 10
- approximated : 1
- unsupported : 0

**Propriétés non intégralement préservées :**

| Propriété | Statut | Détail |
|---|---|---|
| conditional_branches | `approximated` | abstraction topologique conservée, sémantique opaque |

**Statuts d'extraction des nœuds :** extracted=0, declared_by_adapter=5, unresolved=0

### Lecture du graphe de handoffs — topologie extraite

Le SDK OpenAI illustre le cas SYMÉTRIQUE du Flow CrewAI. La topologie de délégation (`agent.handoffs`) est un attribut direct des objets : l'extracteur reconstruit les arêtes par introspection, sans aucune déclaration d'adaptateur ni élément de topologie `unresolved`. Le mapping des nœuds vers les références ACM (agent/prompt/model/outil) reste, lui, déclaré par métadonnées (5 nœud(s) `declared_by_adapter`), exactement comme pour LangGraph — le framework ne connaît que des chaînes de modèle et des fonctions Python. Les trois frameworks couvrent ainsi trois régimes d'introspectabilité à périmètre normatif ACM constant : topologie déclarée (CrewAI Flow), topologie extraite avec conditions opaques signalées (LangGraph), topologie entièrement extraite sans condition opaque (OpenAI Agents SDK).

## Portabilité croisée

Les workflows, exprimés dans les abstractions natives de chaque framework et extraits indépendamment, sont normalisés vers la même représentation ACM sur le périmètre normatif. C'est la preuve d'extraction (plus forte que l'instanciabilité) : ACM comprend et normalise des systèmes natifs existants, pas seulement des spécifications qu'il a lui-même produites. La comparaison LangGraph (topologie extraite) / CrewAI Flow (topologie déclarée) / OpenAI Agents SDK (topologie extraite via handoffs) documente aussi honnêtement les limites d'introspection propres à chaque framework (3 frameworks normalisés vers le même noyau d'agents ACM).

---

*Rapport généré automatiquement — 2026-08-11T01:30:20.946363+02:00*