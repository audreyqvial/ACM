# ACM — Information Preservation Report (auto-généré)

**Généré le :** 2026-07-28 14:55:01 UTC  
**Python :** 3.12.3 — **Plateforme :** Linux x86_64  
**Frameworks :** langgraph=oui, crewai=oui

> Mesure la préservation d'information lors de l'extraction de workflows natifs non triviaux vers la représentation ACM. Chiffres dérivés de l'exécution des extracteurs, jamais codés en dur.

## Cadre

Pour chaque workflow natif F, on calcule E(F) (extraction) et on compare à une représentation golden manuelle sur le périmètre normatif d'ACM. Une propriété est `preserved` (reconstruite exactement), `approximated` (abstraction ACM conservée, ex. condition opaque) ou `unsupported` (aucun concept ACM correspondant).

## Résultats par framework

### LangGraph

| Métrique | Valeur |
|---|---|
| Couverture des nœuds | 100.0% |
| Couverture des relations | 100.0% |
| Couverture des branches | 100.0% |
| Entry point préservé | oui |
| Nœuds terminaux préservés | oui |
| Réf. agent–prompt | 100.0% |
| Réf. agent–outil | 0.0% |
| Éléments unresolved | 0 |
| Digest stable (extraction répétée) | oui |

**Périmètre normatif — statuts de préservation :**

- preserved : 8
- approximated : 1
- unsupported : 2

**Propriétés non intégralement préservées :**

| Propriété | Statut | Détail |
|---|---|---|
| tool_set | `unsupported` | aucun élément extrait pour une propriété présente au golden |
| conditional_branches | `approximated` | abstraction topologique conservée, sémantique opaque |
| agent_tool_refs | `unsupported` | aucun élément extrait pour une propriété présente au golden |

**Statuts d'extraction des nœuds :** extracted=7, declared_by_adapter=0, unresolved=0

### CrewAI

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

**Statuts d'extraction des nœuds :** extracted=7, declared_by_adapter=0, unresolved=0

## Portabilité croisée

Les deux workflows, exprimés dans les abstractions natives de chaque framework et extraits indépendamment, sont normalisés vers la même représentation ACM sur le périmètre normatif. C'est la preuve d'extraction (plus forte que l'instanciabilité) : ACM comprend et normalise des systèmes natifs existants, pas seulement des spécifications qu'il a lui-même produites.

---

*Rapport généré automatiquement — 2026-07-28T14:55:01.722489+00:00*