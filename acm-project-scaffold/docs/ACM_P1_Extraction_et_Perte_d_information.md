# ACM -- Notes de conception

## 1. P1 -- Workflows non triviaux : Extraction ou Construction ?

Pour le **P1 "workflows non triviaux"**, la recommandation est de partir
d'une **EXTRACTION**, et non d'une construction ACM-first.

### Pourquoi l'extraction ?

L'objectif scientifique est de démontrer qu'ACM est capable de
**normaliser des workflows natifs existants**, et non uniquement de
projeter une représentation ACM vers un framework.

Pipeline recommandé :

``` text
Native LangGraph/CrewAI workflow
        ↓
Extraction
        ↓
Canonical ACM representation
        ↓
Validation against golden oracle
        ↓
Optional reprojection
```

Cette approche permet de démontrer : - la préservation de la structure
pertinente ; - la normalisation framework-indépendante ; - la fidélité
de l'extraction vis-à-vis d'un workflow réel.

La construction ACM → Framework reste utile comme test secondaire.
Étape 1 — Créer deux workflows natifs non triviaux
Ils doivent être conçus indépendamment dans chaque framework.
LangGraph
Par exemple :
START
  ↓
Router
  ├── condition A → Researcher
  │                     ↓
  │                  Reviewer
  │                     ↓
  └── condition B → DirectResponder
                        ↓
                       END

Propriétés minimales :
4 à 5 nœuds ;
branche conditionnelle ;
convergence ;
état partagé ;
au moins un outil ;
plusieurs agents ;
éventuellement une boucle bornée Reviewer → Researcher.
CrewAI
Il faut utiliser ses abstractions natives :
Flow
  ↓
Routing step
  ├── Research Crew
  │     ├── Researcher
  │     └── Reviewer
  └── Direct Answer Agent

Propriétés minimales :
plusieurs Agent ;
plusieurs Task ;
relations de contexte entre tâches ;
un Crew ;
un Flow avec branchement ;
état de flow ;
au moins un outil.
Les deux workflows n’ont pas besoin d’être syntaxiquement identiques. Ils doivent représenter une même intention fonctionnelle abstraite.

Étape 2 — Extraire les objets natifs
L’extracteur doit produire au minimum :
AgenticSystem
WorkflowDefinition
AgentDefinition
PromptDefinition
ToolDefinition
ModelProfile
ConfigurationRelation

Pour LangGraph, il faut extraire autant que possible :
noms des nœuds ;
entry point ;
arêtes ;
arêtes conditionnelles ;
destinations possibles ;
fonctions ou agents associés ;
schéma d’état ;
outils et prompts explicitement accessibles ;
métadonnées du checkpointer, sans confondre état runtime et configuration.
LangGraph est particulièrement adapté à cette extraction parce que sa topologie est explicite : StateGraph, nœuds, arêtes et transitions conditionnelles sont des objets structurants natifs.
Pour CrewAI :
agents ;
rôles ;
goals ;
backstories ou instructions pertinentes ;
tasks ;
expected outputs ;
agents responsables ;
dépendances de contexte ;
crew ;
process ;
flow steps ;
listeners, routes ou branchements ;
outils ;
état du Flow.
CrewAI distribue sa configuration entre objets Python et éventuellement YAML ; l’extracteur doit donc documenter ce qui est extrait automatiquement et ce qui nécessite des métadonnées explicites.

Point essentiel : ne pas prétendre extraire l’inextractible
Certaines informations ne sont pas toujours introspectables proprement :
contenu d’une closure Python ;
logique arbitraire d’une condition ;
prompt assemblé dynamiquement ;
dépendance cachée dans une fonction ;
outil créé à la volée ;
modèle récupéré depuis une variable externe ;
comportement implicite d’un callback.
Il faut donc prévoir trois statuts :
extracted
declared_by_adapter
unresolved

Exemple :
{
  "condition": {
    "representation": "route_after_review",
    "source": "native_extraction",
    "semantics": "opaque",
    "possible_targets": ["researcher", "finalizer"]
  }
}

L’objectif n’est pas de traduire du code Python arbitraire en logique formelle. L’objectif est de préserver :
la topologie ;
l’identité des composants ;
les dépendances ;
les références ;
la provenance ;
les limites d’extraction.

Étape 3 — Définir un oracle d’extraction
Il ne suffit pas que l’extracteur “ne plante pas”.
Pour chaque workflow natif, définir manuellement une golden ACM representation contenant les éléments attendus :
nœuds attendus
agents attendus
outils attendus
arêtes attendues
branchements attendus
entry node
termination nodes
relations de contexte

Puis comparer :
extract(native_workflow)
vs
golden_acm_graph

Les comparaisons doivent porter sur une forme canonique, pas sur les UUID ou timestamps.
Métriques possibles
couverture des nœuds ;
couverture des relations ;
préservation de l’entry point ;
préservation des nœuds terminaux ;
préservation des branches ;
préservation des références agent–prompt–outil ;
nombre d’éléments unresolved ;
stabilité du digest après extraction répétée.

Étape 4 — Ajouter une construction comme test secondaire
Une fois l’extraction validée, la construction reste utile pour vérifier :
ACM extrait
→ projection framework

Mais je ne viserais pas un round trip exact :
Framework A
→ ACM
→ Framework A

car les abstractions ne sont pas bijectives.
Je viserais plutôt une équivalence structurelle limitée :
native workflow
→ ACM
→ projected workflow

avec préservation de :
l’ensemble des agents ;
l’entrée ;
les sorties ;
les transitions déclarées ;
les dépendances essentielles ;
les permissions et outils ;
les relations de branchement représentables.
La logique Python arbitraire et les détails internes du framework peuvent légitimement être perdus.

------------------------------------------------------------------------

# 2. Définition formelle d'une perte d'information

## Cadre

Soit : - **F** : un workflow natif ; - **A** : sa représentation ACM.

L'extracteur est **E : F → A**.

## Préservation de l'information

Soit **P** l'ensemble des propriétés que le métamodèle ACM prétend
représenter.

Une extraction est **sans perte** lorsque toutes ces propriétés sont
préservées :

> πₚ(F) = πₚ(E(F))

Autrement dit, toutes les propriétés relevant du périmètre d'ACM restent
reconstructibles après extraction.

## Définition de la perte d'information

La perte d'information correspond à l'ensemble des propriétés
appartenant au périmètre d'ACM qui ne peuvent plus être reconstruites
après extraction.

Conceptuellement :

> Loss(F,E) = { propriétés non préservées }

## Trois catégories

### Preserved

La propriété est reconstruite exactement.

### Approximated

La propriété est représentée par une abstraction ACM, avec une perte de
précision.

### Unsupported

Le métamodèle ACM ne possède aucun concept équivalent.

## Définition normative

> **Information loss** is the inability of an ACM extraction or
> projection to preserve a property that belongs to the normative
> representational scope of the ACM metamodel.

Une propriété est : - **preserved** si elle est reconstruite sans
modification sémantique ; - **approximated** si seule une abstraction
ACM est conservée ; - **unsupported** si aucun concept ACM correspondant
n'existe.

## Complétude d'un adaptateur

Un adaptateur est **complet relativement à ACM** si toutes les
propriétés normatives définies par ACM sont préservées.

L'objectif n'est pas de préserver toutes les caractéristiques d'un
framework, mais uniquement celles appartenant au périmètre normatif
d'ACM.
