# Audit de cohérence
## ACM – Cohérence entre le POC de référence et les sections 6–7 de l'article

Version de référence :
- Article : ACM.pdf
- Implémentation Python : archive du POC
- Source de vérité : article PDF
- Périmètre : sections 6 (Operationalization) et 7 (Evaluation)

---

# Résumé exécutif

## Évaluation globale

| Domaine | État |
|---------|:----:|
| Cohérence conceptuelle | 🟢 Très bonne |
| Cohérence architecture ↔ implémentation | 🟢 Très bonne |
| Cohérence protocole expérimental | 🟢 Bonne |
| Cohérence résultats ↔ POC | 🟡 Bonne avec quelques réserves |
| Risque pour une soumission arXiv | 🟡 Modéré |

Le prototype soutient correctement les affirmations principales des sections 6 et 7.

En revanche, plusieurs affirmations quantitatives reposent encore sur les rapports générés automatiquement. Elles devront être systématiquement synchronisées avec la version exacte du dépôt publiée.

---

# 1. Audit de la section 6 – Operationalization

## 6.1 Reference Architecture

### Conforme

Le découpage annoncé dans l'article est cohérent avec l'architecture réellement implémentée.

On retrouve bien les quatre responsabilités :

- Framework adapters
- Normalization layer
- Governance kernel
- Runtime interface

La séparation entre extraction spécifique au framework et gouvernance indépendante est cohérente avec l'organisation du POC et avec le positionnement scientifique du papier. Le texte insiste correctement sur le fait que l'exécution reste externe à ACM et que le noyau ne manipule que des objets ACM normalisés. :contentReference[oaicite:2]{index=2}

**Statut :**
🟢 Conforme

---

## 6.2 Projection Pipeline

### Conforme

Le pipeline décrit :

LangGraph/CrewAI
→ Adaptateur
→ Normalisation
→ ACI
→ Gouvernance

correspond exactement à l'objectif du POC.

La projection est bien présentée comme une traduction vers un modèle commun, et non comme une exécution.

Aucune incohérence détectée.

**Statut :**
🟢 Conforme

---

## 6.3 Framework Adapters

### Conforme avec le périmètre

Le manuscrit ne revendique que :

- LangGraph
- CrewAI

Le projet est cohérent avec cette décision de périmètre, les autres frameworks étant explicitement reportés en Future Work. :contentReference[oaicite:3]{index=3}

Le niveau d'ambition est correctement calibré.

**Statut :**
🟢 Conforme

---

## 6.4 Governance Algorithms

### Observation

Le moteur implémente effectivement :

- validation structurelle ;
- calcul déterministe ;
- propagation ;
- replay ;
- invariants.

Ces mécanismes sont cohérents avec la sémantique définie dans les sections 4 et 5.

En revanche, l'article gagnerait à montrer explicitement les quatre algorithmes principaux (projection, validation, propagation, runtime integration) plutôt que de décrire essentiellement l'architecture. Cette amélioration avait déjà été identifiée lors des audits de structure. :contentReference[oaicite:4]{index=4}

**Statut :**
🟢 Conforme
🟡 Présentation perfectible

---

## 6.5 Reference Implementation

### Conforme

Le prototype joue bien le rôle annoncé :

- implémentation de référence ;
- démonstrateur ;
- artefact expérimental.

Le papier ne présente pas le prototype comme la contribution scientifique principale.

C'est cohérent avec le positionnement général de l'article.

**Statut :**
🟢 Conforme

---

# 2. Audit de la section 7 – Evaluation

## Positionnement scientifique

Très bonne cohérence.

La section évalue :

- le modèle ;
- les algorithmes ;
- la projection ;
- la faisabilité.

Elle n'évalue pas :

- les performances d'exécution des frameworks.

Cette distinction est correctement respectée dans le manuscrit. :contentReference[oaicite:5]{index=5}

---

## RQ1 – Expressiveness

### Conforme

Le POC couvre :

- ACI ;
- baselines ;
- lifecycle ;
- runtime ;
- assurance ;
- relations.

Les scénarios normatifs couvrent effectivement ces dimensions.

**Statut :**
🟢 Conforme

---

## RQ2 – Governance Consistency

### Conforme

Les scénarios couvrent :

- propagation ;
- invariants ;
- replay ;
- drift ;
- transitions.

Le moteur déterministe soutient correctement cette affirmation.

**Statut :**
🟢 Conforme

---

## RQ3 – Cross-Framework Portability

### Conforme

Le manuscrit revendique une portabilité démontrée uniquement entre LangGraph et CrewAI.

Cette affirmation est cohérente avec le périmètre du POC.

Le papier évite désormais d'affirmer une indépendance universelle.

C'est scientifiquement défendable.

**Statut :**
🟢 Conforme

---

## RQ4 – Implementation Feasibility

### Conforme

Le prototype Python démontre :

- faisabilité ;
- déterminisme ;
- implémentation locale.

Le manuscrit reste prudent.

Aucune surinterprétation détectée.

**Statut :**
🟢 Conforme

---

# 3. Cohérence des scénarios normatifs

Le découpage annoncé :

A : configuration
B : propagation
C : runtime
D : agents dynamiques
E : portabilité

est cohérent avec le modèle ACM et couvre bien les principales dimensions de la spécification. :contentReference[oaicite:6]{index=6}

Point positif :

les scénarios sont organisés selon les mécanismes de gouvernance, et non selon les modules logiciels.

---

# 4. Cohérence des rapports expérimentaux

## Point positif

Les rapports récents montrent une forte maturation :

- scénarios déclaratifs ;
- validation déterministe ;
- séparation des fixtures ;
- rapports consolidés.

Ils soutiennent correctement le discours scientifique.

---

## Réserve

Les valeurs numériques doivent impérativement rester synchronisées entre :

- rapport consolidé ;
- article ;
- dépôt.

L'article indique notamment :

- 277 tests ;
- aucun échec ;
- aucun test ignoré.

Ces chiffres devront correspondre exactement à la version archivée du dépôt au moment de la diffusion. 

---

# 5. Écarts identifiés

## E1 – Niveau de discours

La section 6 contient encore quelques phrases qui interprètent les bénéfices ("framework-independent", "preserves semantics", etc.) alors qu'elles relèvent davantage de la Discussion.

Impact :
Faible.

Correction :
Déplacer ces interprétations vers la section 8.

---

## E2 – Gouvernance Algorithms

La section 6 gagnerait à présenter explicitement les quatre algorithmes structurants.

Impact :
Faible.

Correction :
Ajouter les pseudo-codes correspondant au moteur réellement implémenté.

---

## E3 – Synchronisation des métriques

Les chiffres de validation doivent être gelés sur la version finale du dépôt.

Impact :
Modéré.

Correction :
Regénérer tous les rapports avant la soumission.

---

# 6. Éléments particulièrement solides

Le prototype soutient très bien les affirmations suivantes :

✓ séparation configuration / exécution

✓ projection framework → ACM

✓ gouvernance indépendante du framework

✓ propagation déterministe

✓ replay

✓ invariants exécutables

✓ agents dynamiques

✓ validation basée sur des scénarios normatifs

Ces points apparaissent cohérents entre :

- le code ;
- les rapports ;
- le manuscrit.

---

# 7. Éléments qui doivent rester formulés avec prudence

Les formulations suivantes doivent rester mesurées :

- "framework-independent"

→ préférer :

"initial evidence of framework portability"

- "scalable"

→ préciser le périmètre effectivement évalué

- "general"

→ rappeler que deux frameworks seulement ont été étudiés.

---

# Conclusion

## Niveau de confiance

| Domaine | Note |
|---------|:----:|
| Fidélité article ↔ POC | 9.5 / 10 |
| Cohérence scientifique | 9.7 / 10 |
| Cohérence expérimentale | 9.2 / 10 |
| Risque de contradiction interne | Faible |

Le POC constitue une implémentation de référence cohérente avec les sections 6 et 7 du manuscrit.

Les rares écarts concernent essentiellement :

- la présentation des algorithmes ;
- la séparation plus nette entre Operationalization et Discussion ;
- la synchronisation finale des métriques expérimentales.

Je ne vois pas, à ce stade, de contradiction conceptuelle majeure entre l'implémentation et les affirmations portées par l'article.