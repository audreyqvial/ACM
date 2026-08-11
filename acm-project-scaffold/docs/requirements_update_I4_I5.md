# Note de mise à jour des requirements — Invariants I4 et I5

**Statut :** proposition de modification normative pour ACM Lifecycle and State
Propagation Model v0.1 → v0.2 (§23).

**Origine :** revue technique de l'implémentation de référence (point §5,
« Alignement I4 / I5 »).

---

## Constat

La spécification v0.1 formule I4 et I5 sur la qualité et l'assurance
**effectives** :

    I4 (ACM-ASSURANCE-001) : lifecycle(x) = validated ⇒ effectiveAssurance(x) = assessed
    I5 (ACM-QUALITY-001)   : lifecycle(x) = validated ⇒ effectiveQuality(x) ≠ nok

L'implémentation de référence vérifie ces invariants sur les états **déclarés**
(intrinsèques), et non effectifs. La revue signale l'écart et recommande, je
cite, « de mettre à jour la spécification afin de conserver la séparation entre
état intrinsèque et état effectif » plutôt que de modifier le code.

Cette note formalise cette recommandation, qui est retenue.

## Justification

Vérifier I4/I5 sur l'état **effectif** entre en contradiction directe avec le
principe fondateur du §3.4 (« propagation restrictive plutôt que destructive »).

Contre-exemple, tiré du scénario B (§24.2) :

- un agent `A1` est `validated`, déclaré `ok` / `assessed` ;
- une dépendance `T1` (outil) devient `nok` ;
- par propagation, `A1.effective_quality = nok` **sans** que sa qualité
  intrinsèque change — c'est le comportement voulu, qui préserve la provenance
  du jugement et bloque l'éligibilité plutôt que de réécrire l'état déclaré.

Si I5 portait sur l'effectif, ce scénario **violerait** I5, alors qu'il illustre
précisément le fonctionnement correct du modèle. La contradiction est
structurelle, pas accidentelle : dès qu'une dépendance dégrade la qualité
effective d'un composite validé, l'invariant effectif est enfreint par
construction.

## Modification proposée

Reformuler I4 et I5 pour qu'ils portent explicitement sur l'état **déclaré**
(intrinsèque), qui est le seul niveau où la cohérence de promotion a un sens :

    I4 (ACM-ASSURANCE-001) : lifecycle(x) = validated ⇒ declaredAssurance(x) = assessed
    I5 (ACM-QUALITY-001)   : lifecycle(x) = validated ⇒ declaredQuality(x) ≠ nok

Sémantique : *une révision ne peut pas être promue `validated` alors qu'elle est
déclarée `nok` ou non `assessed`.* La dégradation ultérieure de la qualité ou de
l'assurance **effective** par propagation d'une dépendance n'enfreint pas ces
invariants ; elle se traduit par un blocage d'éligibilité (§17) et un impact
(§11), conformément au §3.4.

## Conséquence pour la conformité (§28)

Aucune. Une implémentation conforme continue de vérifier I1→I14 ; seuls les
énoncés de I4 et I5 sont précisés. L'implémentation de référence est déjà
alignée sur cette formulation (voir `acm/invariants.py`, fonctions
`i4_validated_implies_assessed` et `i5_validated_excludes_nok`, et les tests
`tests/test_invariants.py::test_i5_validated_not_nok_ok` /
`test_i5_violation_declared_nok_while_validated`).

## Portée

Cette note ne modifie que I4 et I5. Les douze autres invariants restent
inchangés. Elle est indépendante des autres correctifs issus de la revue
(identité des preuves, staleness, environnement, politique absente, qualité
dérivée des preuves, intégrité du graphe, contrat de données), qui sont, eux,
des corrections d'implémentation et non des modifications de la spécification.
