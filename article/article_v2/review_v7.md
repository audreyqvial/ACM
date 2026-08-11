# Analyse quantitative d'impacts
## Comment casser la circularité ?

Aujourd'hui, la chaîne de preuve est essentiellement :  

ACM → implémentation ACM → tests ACM → résultats ACM  

Les quatre éléments sont définis par les auteurs.  

Un reviewer peut donc dire :  

"Vous vérifiez que votre implémentation respecte votre propre spécification."  

Ce n'est pas faux.  

En revanche, il existe plusieurs moyens de casser cette circularité.  

1. Niveau 1 — Déjà réalisé : validation croisée entre frameworks  
  
L'ajout d'OpenAI Agents SDK améliore déjà la situation.  

Le noyau ACM reste identique alors que les projections proviennent de trois paradigmes différents :  

- graphe explicite (LangGraph),  
- orchestration rôle/tâche (CrewAI),  
- délégation par handoffs (OpenAI Agents SDK).  

Cela montre que la même sémantique gouverne des représentations natives différentes, ce qui est une validation indépendante du moteur lui-même.  

Mais cela ne suffit pas complètement.  

2. Niveau 2 — Ajouter un oracle externe  

La meilleure façon de casser la circularité est d'introduire un résultat qui n'est pas calculé par ACM.  

Par exemple, pour l'analyse d'impact :  

un expert humain réalise une analyse manuelle,  
ACM calcule sa propagation,  
on compare les deux.
   
Tu as commencé à faire cela dans le nouveau rapport d'impact :  

13 ACI,  
18 relations,  
analyse manuelle exhaustive,  
comparaison exacte,  
aucun faux positif,  
aucun faux négatif.  


## Comment rendre l'analyse d'impact quantitative ?


Aujourd'hui, ton papier dit essentiellement :  

"ACM calcule correctement les impacts."  

Il faudrait aller plus loin :  

"ACM permet également de mesurer l'impact."  

Autrement dit, transformer l'analyse d'impact en métrique.  

1. Première métrique : **taille de propagation**  

La plus simple :  

$ImpactSize(v)=∣Reach(v)∣$
  
où $Reach(v)$ est l'ensemble des ACI atteints par la propagation.  

Exemple :  

modification d'un prompt :  
Prompt  
   ↓  
Agent  
   ↓  
Workflow  
   ↓  
Baseline  
  
Impact = 4.  

2. Deuxième métrique : **profondeur**    

Toutes les propagations n'ont pas la même portée.    

On peut définir :    

$ImpactDepth(v)= max(dist(v,u))
u∈Reach(v)$    

Cela distingue :    

- propagation locale,    
- propagation profonde.    

3. Troisième métrique : **poids**  

Toutes les dépendances ne sont pas équivalentes.  

On peut associer un poids :  

depends_on = 1  
composed_of = 2  
baseline_member = 3  
runtime_reference = 1  

et calculer :  

$ImpactWeight(v)=∑w(u)
u∈Reach(v)$  

Ce n'est plus seulement un nombre de nœuds.  

4. Quatrième métrique : **propagation normalisée** 

Pour comparer plusieurs systèmes :  

$ImpactRatio(v)=∣Reach(v)∣/ ∣V∣$  
  
avec :  

0 : impact local,  
1 : impact global.  

Très pratique pour comparer des graphes de tailles différentes.  

5. Cinquième métrique : **précision de la propagation**  

Puisque tu réalises déjà une comparaison avec une analyse manuelle, tu peux définir :

$Precision=∣P∩M∣/∣P∣$

$Recall=∣P∩M∣/∣M∣$

où :  

P = impacts prédits par ACM,  
M = impacts identifiés par l'expert.  

Dans ton exemple actuel :  

faux positifs = 0,  
faux négatifs = 0,  

donc :  
  
Precision = 1,  
Recall = 1.  

Cette mesure est indépendante du moteur ACM, puisqu'elle compare le résultat à un oracle humain.  

Sixième métrique : **coût évité**  

C'est probablement la plus parlante pour un lecteur industriel.  

Si une analyse manuelle nécessite l'inspection de N éléments et qu'ACM n'en propage que P, on peut définir :  

$InspectionReduction=1−N/P$  

ou, si l'on compare les inspections réellement nécessaires avant et après assistance par ACM :  

$InspectionReduction=1−N_{assisté}/N_{manuel}$  

Cette métrique exprime directement le gain opérationnel.  

## Mettre en place un scenario experimental pour mesurer ces 5 métriques
Elle permettrait de tester simultanément :  

- la portabilité de l’analyse d’impact ;
- l’indépendance du noyau ACM ;
- la précision de la propagation ;
- le gain opérationnel par rapport à une analyse manuelle.  
  
Les nouveaux rapports montrent déjà que les trois frameworks couvrent trois régimes différents d’introspectabilité, tout en étant normalisés vers le même périmètre ACM. Le rapport d’impact fournit par ailleurs un premier oracle manuel sur un graphe de 13 ACI et 18 relations.  

Scénario expérimental proposé
Hypothèse

Pour un même système agentique fonctionnel exprimé dans trois frameworks distincts, ACM identifie les mêmes impacts de gouvernance après modification d’un composant partagé, avec une précision et un rappel élevés, tout en réduisant le coût d’inspection manuelle.

Il faut éviter de comparer directement les objets natifs des frameworks, car leurs granularités diffèrent. La comparaison doit porter sur les représentations ACM extraites indépendamment.

1. Construire trois systèmes fonctionnellement équivalents

Le même cas d’usage est implémenté séparément dans :

LangGraph ;
CrewAI ;
OpenAI Agents SDK.

Une topologie commune possible :

Entry / Triage
       |
       +--> Direct Agent
       |
       +--> Research Agent
                 |
                 v
             Reviewer
                 |
                 v
             Finalizer

Chaque implémentation utilise les mêmes catégories d’artefacts :

cinq agents ;
cinq prompts ;
un modèle partagé ;
un outil de recherche ;
éventuellement une policy commune ;
un workflow ou une structure de délégation.

Les systèmes ne doivent pas être générés à partir d’une spécification ACM commune. Ils doivent être écrits dans les abstractions natives des frameworks, puis extraits indépendamment. Cette contrainte évite qu’ACM soit à la fois la source et l’oracle de l’expérience.

Les rapports actuels possèdent déjà des cas proches :

LangGraph avec branche conditionnelle ;
CrewAI Flow+Crew ;
OpenAI Agents SDK avec graphe de handoffs.
2. Définir une perturbation commune

Le meilleur changement racine est le remplacement d’un modèle partagé :
``̀ bash
aci:model:shared-llm
revision r1
→
revision r2
``̀

Ce choix est préférable à un changement de prompt, car il doit affecter plusieurs agents et produire une propagation transitive vers les workflows.

Pour chacun des trois systèmes :
``̀ bash
Shared Model
   ├── Research Agent
   ├── Reviewer
   └── Finalizer
          ↓
      Workflow / Crew / Handoff Graph
          ↓
      Release Baseline
``̀   
On peut également prévoir trois classes de perturbations afin de vérifier que les métriques discriminent correctement :

| Classe | Changement |	Impact attendu |
| -------- | -------- | -------- |
| Local	| prompt du Finalizer | faible |
| Intermédiaire |outil du Research Agent | moyen |
| Global | modèle partagé | élevé |
  
## Construire un oracle indépendant

Pour éviter la circularité, l’ensemble attendu des impacts ne doit pas être produit par ACM.

Pour chaque framework, un oracle manuel doit être construit à partir :

du code natif ;
des relations explicitement observables ;
de la documentation de la fixture expérimentale ;
d’une inspection transitive complète.

L’oracle est $M_{f}(c)$

où :

$f$ est le framework ;
$c$ est le changement ;
$M_{f}(c)$ est l’ensemble des artefacts affectés selon l’analyse indépendante.

ACM produit ensuite $P_{f}(c)$

La comparaison porte sur $M_{f}(c)$ et $P_{f}(c)$


Idéalement, l’oracle est établi avant l’exécution de la propagation ACM, ou conservé dans un fichier séparé dont le moteur ne dépend pas.

## Mesurer les cinq métriques
### Taille de l’impact
$ImpactSize_{f}(c) = |P_{f}(c)|$

  
Elle indique combien d’ACI sont affectés.    
  
Exemple de tableau :  

|Framework	|Local	|Intermédiaire|	Global|
| ------ | ------ | ------ | ------ |
|LangGraph	|3	|6	|10|
|CrewAI	|3	|6	|10|
|OpenAI Agents SDK|	3	|6	|10|
  
Une égalité parfaite n’est pas obligatoire si les représentations ACM contiennent des différences justifiées. Il faut toutefois expliquer chaque différence.  

### Profondeur d’impact
$ImpactDepth_{f}(c) = \max dist(c, u), u \in P_{f}(c)$


Elle mesure la longueur maximale d’une chaîne de propagation.  

Exemple :  
̀ ``bash
Model  
→ Agent  
→ Workflow  
→ Baseline  
̀ ``  
donne une profondeur de 3.

### Ratio d’impact
$ImpactRatio_{f}(c) = ∣P_{f}(c)|/|V_{f}|$  


Cette métrique permet de comparer des graphes de tailles différentes.  

Elle est indispensable, car les projections CrewAI, LangGraph et OpenAI Agents SDK ne produisent pas forcément exactement le même nombre d’ACI.  

### Précision et rappel
$Precision_{f}(c)=∣P_{f}(c) \bigcap M_{f}(c)∣/ ∣P_{f}(c)$  
$ Recall_{f}(c)=∣P_{f}(c) \bigcap M_{f}(c)∣/ ∣M_{f}(c)$  


**Interprétation :**

- précision faible : ACM produit des faux positifs ;  
- rappel faible : ACM manque des impacts ;  
- les deux à 1 : accord exact avec l’oracle.  

Le rapport actuel fournit déjà un cas avec précision et rappel égaux à 1, puisque l’ensemble ACM coïncide exactement avec l’analyse manuelle exhaustive.  

### Réduction du coût d’inspection

Il faut définir précisément ce qu’est une inspection.


Une inspection correspond à l’examen manuel d’un ACI ou d’une relation afin de déterminer si le changement peut s’y propager.  

On mesure :  

$InspectionReduction_{f}(c)=1−(I_{f}^{ACM}(c) / I_{f}^{Manual}(c))$
  
  
Deux variantes sont possibles.  

**Variante stricte**
Manual : nombre d’objets ou relations examinés pendant l’analyse exhaustive ;  
ACM : nombre d’objets à vérifier après que l’outil a fourni l’ensemble affecté.  
   
Cette variante mesure le coût humain résiduel.   

**Variante algorithmique**  
Manual : inspections humaines ;  
ACM : une requête de propagation.  

Le rapport actuel utilise cette seconde représentation : 10 inspections manuelles contre une propagation ACM.  

Pour l’article scientifique, la variante stricte est plus défendable, car une requête informatique et une inspection humaine ne sont pas directement comparables.  

### Protocole expérimental
  
Pour chaque framework f et chaque changement c :  
  
- Construire le système natif.
- Extraire sa représentation ACM.
- Vérifier la stabilité du digest.
- Construire l’oracle manuel $M_{f}(c)$.
- Appliquer la modification racine.
- Exécuter la propagation ACM.
- Collecter $P_{f}(c)$
- Calculer les cinq métriques.  
- Comparer les résultats entre frameworks.  
- Répéter l’expérience afin de vérifier le déterminisme.  

Avec trois frameworks et trois perturbations, cela donne :3×3=9

cas expérimentaux principaux.  
  
C’est suffisamment substantiel sans devenir disproportionné.  

### Résultats supplémentaires utiles

Je mesurerais aussi deux variables secondaires.  

Temps de calcul  
$T_{f}(c)$

Même si les graphes sont petits, cela documente le coût du prototype.  

Il ne faut pas en faire une revendication de performance, seulement une mesure de reproductibilité.
  
Nombre d’itérations du point fixe  
$K_{f}(c)$

Cette valeur relie directement l’expérience à la formalisation de la propagation.  

Le rapport actuel montre déjà des convergences entre une et trois itérations selon les scénarios.  

### Résultat attendu et hypothèses réfutables

L’expérience doit prévoir des critères susceptibles d’échouer.  
  
Par exemple :  
  
**H1 — Exactitude**
$Precision_{f}(c)=1∧Recall_{f}(c)=1$

pour tous les cas couverts par la sémantique normative.

**H2 — Invariance sémantique**

Pour des systèmes fonctionnellement équivalents :  

$ImpactRatio_{LG}(c)≈ImpactRatio_{CA}(c)≈ImpactRatio_{OA}(c)$

Il vaut mieux parler d’équivalence ou de proximité des ratios que d’égalité absolue, puisque les projections peuvent différer en granularité.

**H3 — Réduction de l’inspection**  
$InspectionReduction_f (c)>0$  
  
pour chaque framework.  
  
**H4 — Déterminisme**   
  
Les répétitions d’une même expérience produisent :    

- le même ensemble affecté ;
- le même digest fonctionnel ;
- le même nombre d’itérations, sauf métadonnées non sémantiques.  

### Attention à une difficulté méthodologique

Le principal risque est de fabriquer trois graphes ACM identiques en amont puis de simplement les instancier dans les frameworks.  

Cela recréerait la circularité.  

La séquence correcte est :   
`̀̀ `
Native LangGraph system
        ↓ extraction

Native CrewAI system
        ↓ extraction

Native OpenAI Agents SDK system
        ↓ extraction

Three independently obtained ACM graphs
        ↓
Impact experiment
`̀̀ `
et non :
`̀̀ `bash
One ACM graph
        ↓
Generated into three frameworks
        ↓
Reimported into ACM
`̀̀ `

Le rapport de préservation précise déjà que les workflows sont exprimés dans les abstractions natives puis extraits indépendamment ; il faut préserver strictement cette méthode.

9. Forme recommandée pour le rapport

Le rapport auto-généré pourrait contenir :
`̀̀ `bash
Experiment
├── framework
├── change_id
├── native_graph_size
├── acm_graph_size
├── relation_count
├── oracle_affected
├── predicted_affected
├── true_positive
├── false_positive
├── false_negative
├── impact_size
├── impact_depth
├── impact_ratio
├── precision
├── recall
├── manual_inspections
├── assisted_inspections
├── inspection_reduction
├── fixed_point_iterations
└── elapsed_ms  
`̀̀ `