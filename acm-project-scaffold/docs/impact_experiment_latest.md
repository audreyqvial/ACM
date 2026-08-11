# Rapport — Expérience quantitative d'impact

Généré : 2026-08-10 23:24:07 UTC

Chaîne : système natif-équivalent → moteur ACM (point fixe) → P_f(c) → comparaison à l'oracle figé (vérifié par digest). Le résultat publié provient du moteur, pas de `reach()`.

## Vérifications transverses

- Cas exécutés : 9
- Oracles vérifiés par digest : tous
- Déterminisme (répétitions identiques) : oui
- Cohérence statique P_f(c) ⊆ reach(root) : tenue partout

## ImpactSize |P_f(c)|

| Framework | local | intermediate | global |
| --- | --- | --- | --- |
| crewai | 2 | 2 | 5 |
| langgraph | 2 | 2 | 5 |
| openai-agents | 2 | 2 | 5 |

## ImpactRatio |P_f(c)| / |V|

| Framework | local | intermediate | global |
| --- | --- | --- | --- |
| crewai | 0.182 | 0.182 | 0.455 |
| langgraph | 0.182 | 0.182 | 0.455 |
| openai-agents | 0.182 | 0.182 | 0.455 |

## Précision / Rappel vs oracle figé

| Framework | Classe | Precision | Recall | F1 | FP | FN |
| --- | --- | --- | --- | --- | --- | --- |
| crewai | local | 1.00 | 1.00 | 1.00 | 0 | 0 |
| crewai | intermediate | 1.00 | 1.00 | 1.00 | 0 | 0 |
| crewai | global | 1.00 | 1.00 | 1.00 | 0 | 0 |
| langgraph | local | 1.00 | 1.00 | 1.00 | 0 | 0 |
| langgraph | intermediate | 1.00 | 1.00 | 1.00 | 0 | 0 |
| langgraph | global | 1.00 | 1.00 | 1.00 | 0 | 0 |
| openai-agents | local | 1.00 | 1.00 | 1.00 | 0 | 0 |
| openai-agents | intermediate | 1.00 | 1.00 | 1.00 | 0 | 0 |
| openai-agents | global | 1.00 | 1.00 | 1.00 | 0 | 0 |

## Réduction du coût d'inspection (variante stricte)

| Framework | Classe | Manual | Assisted | Reduction |
| --- | --- | --- | --- | --- |
| crewai | local | 13 | 2 | 0.846 |
| crewai | intermediate | 13 | 4 | 0.692 |
| crewai | global | 13 | 5 | 0.615 |
| langgraph | local | 13 | 2 | 0.846 |
| langgraph | intermediate | 13 | 4 | 0.692 |
| langgraph | global | 13 | 5 | 0.615 |
| openai-agents | local | 13 | 2 | 0.846 |
| openai-agents | intermediate | 13 | 4 | 0.692 |
| openai-agents | global | 13 | 5 | 0.615 |

## Reproductibilité

| Framework | Classe | K itérations | ms | Déterministe |
| --- | --- | --- | --- | --- |
| crewai | local | 3 | 2.15 | oui |
| crewai | intermediate | 3 | 2.11 | oui |
| crewai | global | 3 | 2.12 | oui |
| langgraph | local | 3 | 2.24 | oui |
| langgraph | intermediate | 3 | 2.07 | oui |
| langgraph | global | 3 | 2.13 | oui |
| openai-agents | local | 3 | 2.18 | oui |
| openai-agents | intermediate | 3 | 2.14 | oui |
| openai-agents | global | 3 | 2.15 | oui |

## Reassessment de baseline (signal dérivé, hors P_f(c))

La baseline released est immuable : un changement d'un required_item déclenche un reassessment opérationnel externe (§6.5), calculé à partir de P_f(c). La baseline n'apparaît pas dans l'ensemble affecté.

| Framework | Classe | Reassessment | Déclencheurs |
| --- | --- | --- | --- |
| crewai | local | requis | aci:agent:finalizer, aci:prompt:finalize, aci:workflow:main |
| crewai | intermediate | requis | aci:agent:researcher, aci:tool:web-search, aci:workflow:main |
| crewai | global | requis | aci:agent:direct, aci:agent:finalizer, aci:agent:researcher, aci:agent:reviewer, aci:model:shared-llm, aci:workflow:main |
| langgraph | local | requis | aci:agent:finalizer, aci:prompt:finalize, aci:workflow:main |
| langgraph | intermediate | requis | aci:agent:researcher, aci:tool:web-search, aci:workflow:main |
| langgraph | global | requis | aci:agent:direct, aci:agent:finalizer, aci:agent:researcher, aci:agent:reviewer, aci:model:shared-llm, aci:workflow:main |
| openai-agents | local | requis | aci:agent:finalizer, aci:prompt:finalize, aci:workflow:main |
| openai-agents | intermediate | requis | aci:agent:researcher, aci:tool:web-search, aci:workflow:main |
| openai-agents | global | requis | aci:agent:direct, aci:agent:finalizer, aci:agent:researcher, aci:agent:reviewer, aci:model:shared-llm, aci:workflow:main |
