# Revue technique de l'implémentation ACM

## Synthèse

L'implémentation constitue un **bon prototype exécutable de la
spécification ACM v0.1**, avec une architecture claire et une couverture
utile des scénarios. En revanche, elle ne peut pas encore être
considérée comme une **implémentation de référence conforme** à la
spécification normative.

### Résultat des vérifications

-   ✅ 75 tests du cœur passent.
-   ⚠️ La suite complète ne démarre pas avec une installation minimale
    du cœur (`ModuleNotFoundError: langchain_core`).
-   ⚠️ Plusieurs écarts normatifs subsistent autour de l'identité des
    preuves, de la gestion de la *staleness*, de la distinction entre
    politique absente et politique vide, et du calcul de la qualité.

------------------------------------------------------------------------

# Écarts bloquants

## 1. Identité des preuves

La comparaison d'une preuve avec une révision repose actuellement
principalement sur `revision_id`. Le `digest` n'est pas toujours
vérifié, ce qui peut conduire à accepter une preuve ciblant une révision
modifiée.

**Recommandation :** - vérifier systématiquement
`(ACI id, revision_id, digest)`.

**Tests à ajouter :** - même `revision_id`, digest différent ; - même
digest, revision différente ; - digest absent.

------------------------------------------------------------------------

## 2. Gestion de la staleness

Le champ `dependency_snapshot` est présent mais n'est pas exploité dans
le calcul d'applicabilité des preuves.

Conséquence : une preuve peut rester applicable alors qu'une dépendance
a changé.

**Recommandation :** - introduire un état d'applicabilité (`applicable`,
`stale`, `inapplicable`) ; - comparer le snapshot enregistré avec les
dépendances courantes.

------------------------------------------------------------------------

## 3. Contraintes d'environnement

Les contraintes d'environnement sont modélisées mais non utilisées dans
le calcul d'applicabilité.

**Recommandation :** - intégrer l'environnement dans le contexte de
propagation.

------------------------------------------------------------------------

## 4. Politique absente vs politique vide

Le modèle crée systématiquement une politique d'assurance par défaut.

Cela ne permet plus de distinguer :

-   aucune politique déclarée ;
-   politique explicitement vide.

**Recommandation :** - rendre `assurance_policy` optionnelle.

------------------------------------------------------------------------

## 5. Alignement I4 / I5

Le code vérifie actuellement les états **déclarés**, alors que la
version actuelle de la spécification parle des états **effectifs**.

Deux possibilités :

-   modifier le code ;
-   ou mettre à jour officiellement la spécification.

Je recommande de mettre à jour la spécification afin de conserver la
séparation entre état intrinsèque et état effectif.

------------------------------------------------------------------------

## 6. Calcul de qualité

Le résultat des preuves (`pass`, `fail`, `inconclusive`) n'alimente pas
le calcul de qualité.

Il manque une fonction dédiée produisant :

-   OK
-   TO_IMPROVE
-   NOK

indépendamment du calcul d'assurance.

------------------------------------------------------------------------

# Contrat de données

## Immutabilité

Les objets annoncés comme immuables restent modifiables.

**Recommandation :**

-   utiliser `frozen=True` pour les modèles normatifs.

------------------------------------------------------------------------

## Champs supplémentaires

Les champs inconnus sont actuellement acceptés.

**Recommandation :**

-   `extra="forbid"`.

------------------------------------------------------------------------

## Enum

Plusieurs champs restent de simples chaînes (`result`, `aci_type`,
etc.).

**Recommandation :**

-   utiliser des `Enum` pour tous les états normatifs.

------------------------------------------------------------------------

# Intégrité du graphe

À ajouter :

-   détection des révisions dupliquées ;
-   détection des relations dupliquées ;
-   validation des références manquantes ;
-   détection explicite de la non-convergence.

------------------------------------------------------------------------

# Rapport de propagation

Le rapport devrait contenir davantage d'informations :

-   mode d'assurance résolu ;
-   preuves applicables ;
-   preuves rejetées ;
-   preuves stale ;
-   politique résolue ;
-   détails de couverture ;
-   nombre d'itérations ;
-   convergence.

------------------------------------------------------------------------

# Tests prioritaires

## P0

1.  digest incorrect
2.  changement de dependency snapshot
3.  environnement incompatible
4.  politique absente
5.  qualité NOK après preuve bloquante
6.  référence obligatoire manquante
7.  immutabilité
8.  `extra="forbid"`
9.  validation I4/I5
10. exécution du cœur sans extras

## P1

-   preuves multiples couvrant R(x)
-   preuves expirées
-   duplicats
-   cycles
-   indépendance de l'ordre
-   convergence

## P2

Tests property-based (Hypothesis) :

-   monotonie ;
-   invariance à l'ordre ;
-   idempotence ;
-   stabilité de sérialisation.

------------------------------------------------------------------------

# Priorités de correction

1.  Identité exacte des preuves (`revision_id` + `digest`)
2.  Gestion de la staleness
3.  Politique absente vs vide
4.  Qualité dérivée des preuves
5.  Validation structurelle du graphe
6.  Alignement I4/I5
7.  Immutabilité et `extra="forbid"`
8.  Découpage des tests optionnels

------------------------------------------------------------------------

# Conclusion

Le projet est un **prototype robuste** et proche d'une implémentation de
référence ACM. Les principaux travaux restants concernent les garanties
normatives du moteur d'assurance (identité des preuves, applicabilité,
staleness et contrat de données). Une fois ces points stabilisés,
l'implémentation pourra raisonnablement servir de référence pour
accompagner une publication scientifique.
