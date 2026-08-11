# Revue technique ACM -- Analyse de la version corrigée

*Date de revue : 2026-07-27*

## Résumé exécutif

Cette nouvelle version montre une amélioration sensible par rapport à la
précédente revue. La présence du document `requirements_update_I4_I5.md`
indique que la divergence identifiée entre la spécification et
l'implémentation concernant les invariants **I4** et **I5** a été
officiellement intégrée dans les exigences. Cette évolution aligne
désormais le code et la spécification sur la distinction entre **états
déclarés** et **états effectifs**, ce qui constitue un progrès important
du modèle ACM.

Par ailleurs, l'arborescence montre l'ajout de tests dédiés aux
priorités **P0**, **P1** et **P2**, ce qui traduit une meilleure
couverture des exigences précédemment identifiées.

## Évolutions constatées

### Alignement de la spécification

Le dossier `docs` contient :

-   `requirements_update_I4_I5.md`
-   la revue technique précédente
-   la spécification Lifecycle.

La présence de cette mise à jour confirme que les exigences ont été
adaptées afin de rendre cohérente la séparation entre assurance/qualité
déclarées et effectives.

### Renforcement de la stratégie de tests

La structure des tests comprend désormais :

-   `test_p0_review.py`
-   `test_p1_review.py`
-   `test_p2_properties.py`
-   `test_core_no_extras.py`

Cette organisation correspond aux recommandations formulées lors de la
précédente revue.

### Packaging

Le projet conserve une séparation propre entre :

-   noyau ACM ;
-   adaptateurs ;
-   scénarios ;
-   exemples ;
-   documentation.

Cette architecture reste cohérente avec l'objectif d'une implémentation
de référence.

## Points restant à vérifier

La simple présence des nouveaux tests et des documents ne permet
toutefois pas d'attester automatiquement que :

1.  les règles d'applicabilité des preuves utilisent systématiquement le
    couple `(revision_id, digest)` ;
2.  la staleness des preuves est entièrement calculée à partir du
    `dependency_snapshot` ;
3.  les contraintes d'environnement sont effectivement évaluées ;
4.  les modèles Pydantic sont désormais immuables (`frozen=True`) et
    utilisent `extra="forbid"` ;
5.  le rapport de propagation expose l'ensemble des informations de
    traçabilité attendues.

Ces points méritent une inspection ciblée du code métier avant de
considérer l'implémentation comme totalement conforme à la spécification
normative.

## Évaluation globale

  -----------------------------------------------------------------------
  Domaine                             Évaluation
  ----------------------------------- -----------------------------------
  Architecture                        ✅ Très satisfaisante

  Alignement de la spécification      ✅ Corrigé pour I4/I5

  Organisation des tests              ✅ Forte amélioration

  Séparation du cœur ACM              ✅ Conforme

  Maturité globale                    🟢 Prototype avancé proche d'une
                                      implémentation de référence
  -----------------------------------------------------------------------

## Recommandations

Avant la publication de la première version de référence ACM, je
recommande :

1.  une revue ligne à ligne du moteur de propagation ;
2.  une vérification systématique de chaque invariant normatif ;
3.  un audit de reproductibilité (configuration digest, replay,
    snapshots) ;
4.  une matrice de conformité Requirement → Code → Tests.

## Conclusion

Cette version montre une progression significative par rapport à la
précédente revue. Les correctifs apportés à la spécification (notamment
I4/I5) et l'enrichissement de la stratégie de tests vont dans le bon
sens. Le projet semble désormais entrer dans une phase où les
principales évolutions concernent davantage la robustesse normative et
la validation exhaustive que la conception du modèle lui-même.
