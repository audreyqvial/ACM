# Review de l'article ACM v8
## Méthodologie de review proposée

### Contribution scientifique

Le positionnement est clair et défendable : ACM n'est pas un framework d'orchestration de plus mais une couche de gouvernance framework-independent. La distinction configuration/exécution est le cœur conceptuel et elle est tenue avec discipline tout au long du papier. C'est une vraie contribution d'ingénierie logicielle appliquée à un domaine (systèmes agentiques) où le vide existe effectivement.

**Points forts** : l'extension des principes SCM (revisions immuables, baselines, provenance) aux artefacts agentiques est légitime et bien argumentée ; la formalisation via treillis fini + Knaster-Tarski donne une assise théorique que la plupart des papiers « AgentOps » n'ont pas ; les quatre contributions (représentation, sémantique, projection, opérationnalisation) sont cohérentes.

**Réserve majeure — nouveauté vs. re-packaging** La critique la plus dure qu'un reviewer TSE/TOSEM formulera : à quel point ACM est-il davantage qu'une application soignée de SCM classique + PROV + une couche d'adaptateurs ? La monotonie sur un treillis à 3 éléments (None < Local < Propagated) est un résultat standard ; Knaster-Tarski sur un treillis fini est presque trivial (la convergence par itération croissante suffirait sans invoquer le théorème). L'appareil formel est correct mais surdimensionné par rapport à la profondeur du résultat. Il faut soit assumer cela (« nous formalisons pour la reproductibilité, pas pour la difficulté mathématique »), soit enrichir le treillis d'impact pour justifier l'artillerie.

### Rigueur formelle

* Least fixed point — précision nécessaire : tu affirmes correctement en G.4 que ι* est le plus petit point fixe au-dessus de ι⁽⁰⁾, pas le plus petit point fixe global. C'est bien formulé. Mais l'abstract et la Section 5.7 disent « uniqueness of the least fixed point » sans cette nuance — harmonise, sinon un reviewer formel notera l'imprécision.
* Fonctions de transfert τ_p sous-spécifiées : l'équation (49) introduit τ_p mais son comportement exact reste « determined by the associated propagation policy ». Pour un résultat de monotonie, il faut au minimum garantir que chaque τ_p est monotone ET bottom-preserving — tu l'affirmes (64)-(65) mais sans définir les τ_p explicitement. Donne la table concrète des quatre τ_p (Blocking/Warning/Informational/None → fonction I→I). Sans elle, la preuve repose sur une hypothèse non instanciée.

### Évaluation empirique — le point faible

C'est ici que se joue l'acceptabilité. Les résultats du Tableau 12 sont un signal d'alarme pour tout reviewer.

Precision = Recall = F1 = 1.00 sur les 9 cas, avec des Impact Size (2, 2, 5) et Inspection reduction (0.846, 0.692, 0.615) strictement identiques entre LangGraph, CrewAI et OpenAI Agents SDK. Tu anticipes l'objection en expliquant que les structures de dépendances projetées sont « governance-equivalent », donc les métriques convergent — mais cela affaiblit paradoxalement la démonstration : si les trois frameworks produisent des chiffres identiques par construction, l'évaluation cross-framework ne teste plus rien d'empirique, elle vérifie que ton propre pipeline est déterministe. Un F1 parfait comparé à des reference sets que tu as toi-même établis, non arbitrés par un tiers (tu l'admets honnêtement), n'est pas une validation — c'est une vérification de cohérence interne. Il faut le dire encore plus franchement, ou introduire une vraie variabilité (frameworks avec topologies réellement différentes, cas où la projection perd de l'information et où précision < 1).

**Autres réserves**

N=27 scénarios + 9 cas, tous conçus par l'auteur : « normative scenarios » signifie que tu as écrit à la fois le test et l'oracle. C'est légitime pour un reference model, mais ce n'est pas une évaluation indépendante. Ton honnêteté sur ce point (Section 7, « rather than an independent empirical validation of the universal correctness ») est à ton crédit et doit rester.
Pas de baseline comparative : aucune comparaison avec une approche existante (même un baseline naïf « inspecter tout le graphe »). L'inspection scope reduction est calculée contre l'inspection exhaustive, ce qui est le minimum ; ajoute au moins un point de comparaison.
Rapports expérimentaux exclus : pour juger RQ4 sérieusement, j'ai besoin des rapports que tu as retirés de l'annexe — inventaires de projection, convergence du point fixe (nombre d'itérations réel), digests de reproductibilité. Envoie-les moi si tu veux que je valide cette partie.

### Figures, sémantique, modélisation

Les figures sont nombreuses et de bonne qualité conceptuelle. Remarques :

Figures 1-6 (conceptuelles) : pertinentes, bien légendées. Fig. 3 (four-graph) et Fig. 4 (métamodèle ACI) portent le cœur du modèle — claires.
Figure 8 : dense mais lisible ; bonne synthèse des cinq espaces d'état.
Redondance figures/tables : Tables 8, 9, 10, 13 se recouvrent largement (toutes mappent RQ→evidence→«Supported»). Un reviewer notera que « Supported » partout, répété dans quatre tables, sonne auto-complaisant. Fusionne 8/9/13 en une seule table de synthèse.
Tables 2 et 18 : la colonne ACM avec des ✓ partout face aux ∼/– des autres familles est visuellement du cherry-picking. C'est structurellement vrai (tu définis les capacités que ton modèle couvre), mais présenté ainsi, ça affaiblit la crédibilité. Nuance au moins une ou deux cellules ACM.

### Equations et notations
Incohérence de casse d'état : l'Appendice C définit le lifecycle comme {Draft, Validated, Approved, Released, Deprecated, Archived} (eq. 24) mais la Figure 8 montre {Created, Draft, In Review, Validated, Released}. Les espaces d'état lifecycle ne correspondent pas entre le texte formel et la figure. À réconcilier — c'est exactement le type d'incohérence notation/modèle que ta review précédente (condition 6) pointait déjà.
De même Quality : eq.(25) {Undefined, Valid, Warning, Invalid} vs Figure 8 {Valid, Warning, Invalid, Undefined} — ordre ok, mais vérifie l'ordre partiel car Warning vs Invalid n'est pas clairement ordonné.

## Verdict

En l'état : rejet en Major Revision pour une IEEE Transactions (TSE) ou ACM TOSEM. L'article n'est pas acceptable tel quel pour ces venues de premier rang, essentiellement à cause de (a) l'évaluation dont les résultats parfaits et identiques n'établissent pas ce qu'ils prétendent, (b) la question de nouveauté au-delà du re-packaging SCM, (c) les incohérences formelles (espaces d'état lifecycle divergents figure/texte).

Ce ne sont pas des défauts rédhibitoires — ce sont des corrections faisables. Avec elles, l'article est publiable.

Venues réalistes selon l'effort investi :

Si tu corriges les incohérences formelles + nuances l'évaluation sans nouvelle campagne : IEEE Access (accepte les reference models bien construits, tolère l'évaluation par scénarios normatifs, cycle rapide) — probablement acceptable après revision mineure-à-majeure. C'est à mon sens le meilleur rapport effort/probabilité pour cet article.

Si tu ajoutes une vraie variabilité expérimentale + une baseline comparative + validation à plus grande échelle : viser ACM TOSEM ou IEEE TSE devient défendable, mais compte 1-2 campagnes supplémentaires.

Venue conférence alternative solide : IEEE/ACM ICSE (SEIP track) ou ASE — le format « reference model + operationalization » y passe mieux qu'en journal, et la contribution d'architecture y est mieux valorisée.

# Inclusion des rapports expérimentaux

J'ai lu les rapports. Ils clarifient plusieurs choses et changent mon appréciation sur certains points — mais pas sur le verdict de fond. Voici l'analyse.

## Ce que les rapports apportent (et que l'article sous-exploite)

Trois éléments réels sont dans les données mais absents ou noyés dans le papier :

Le `impact_report_latest.json` contient le seul résultat empirique qui *démontre quelque chose* : sur un graphe de 13 ACI / 18 relations, l'investigation naïve à 1 niveau rate 3 items sur 9 (les `workflow:w0/w1/w2`, affectés transitivement). **Ça, c'est un résultat.** Il oppose ACM à un baseline (l'inspection naïve) et montre un écart mesurable. Or ce cas n'est pas la campagne principale — c'est un rapport annexe. La campagne B, elle, ne compare ACM qu'à son propre oracle.

Le `preservation_report` est plus honnête que le Tableau 11 du papier. Il montre `state_schema: unsupported` sur CrewAI Flow, une distinction extracted (4) vs declared_by_adapter (2/5), et `conditional_branches: approximated` partout. Le papier lisse ça en « 100% / 9-10 preserved ». Les vraies données sont *plus intéressantes* que leur présentation, parce qu'elles exhibent les limites — ce qui est précisément ce qu'un reviewer TOSEM veut voir.

Le `evaluation_report` révèle que `digest_verified: false` et `Oracles vérifiés par digest : INCOMPLET`. Le mécanisme de vérification d'oracle par digest, que le papier présente comme une garantie d'indépendance, **n'est pas activé dans le run**. Un reviewer qui demande les artefacts (ce que je viens de faire) le verra.

## Ta question 1 : enlever Precision/Recall/F1 suffit-il ?

Non, mais ça aide plus que ça ne coûte. Retirer P/R/F1 supprime le signal le plus embarrassant (trois colonnes de `1.00` identiques comparées à ton propre oracle non arbitré). Le problème est que si tu les retires **sans rien mettre à la place**, il ne reste dans la campagne B que `ImpactSize`, `ImpactRatio` et `inspection_reduction` — dont les deux premiers sont identiques par construction entre frameworks, et le troisième est un ratio dérivé mécaniquement de l'impact size (`assisted/manual`). Tu passes d'« évaluation aux résultats trop parfaits » à « évaluation qui ne mesure presque rien ». Pour IEEE Access, ça passe. Pour TOSEM/TSE, non : le reviewer dira que la campagne B ne teste pas d'hypothèse falsifiable.

Le bon mouvement n'est pas *retirer* mais *recadrer* : remplace P/R/F1 par la comparaison **ACM vs inspection naïve** du `impact_report`. Là, précision/rappel ont un sens, parce que le naïf produit de vrais faux négatifs (3/9). Tu gardes une métrique de qualité, mais elle oppose enfin deux méthodes distinctes au lieu d'ACM à lui-même.

## Ta question 2 : ce qu'il faut pour viser TOSEM ou TSE

Le fond du problème n'est pas cosmétique. TOSEM/TSE rejetteront pour trois raisons structurelles, par ordre de gravité :

**1. L'évaluation ne falsifie rien.** Aujourd'hui : scénarios écrits par l'auteur, oracle écrit par l'auteur, moteur qui matche l'oracle. C'est une vérification de conformité implémentation-vs-spécification, pas une évaluation. Il faut au moins un des trois : (a) des systèmes agentiques **tiers, non conçus pour ACM** — repos GitHub réels utilisant LangGraph/CrewAI, projetés à l'aveugle ; (b) une **étude utilisateur** même modeste (5-8 ingénieurs qui font l'impact analysis à la main vs avec ACM, tu mesures temps *et* erreurs) — c'est ça qui transforme « inspection scope reduction » d'un ratio arithmétique en une vraie mesure d'effort humain, ce que le papier admet lui-même ne pas faire ; (c) des cas où **ACM échoue** — configurations où la projection perd de l'information critique, où precision < 1. Un modèle qui ne rate jamais rien dans aucun test n'a pas été testé sur son domaine de rupture.

**2. La nouveauté formelle est mince.** Treillis à 3 éléments + Knaster-Tarski, c'est correct mais un relecteur TSE dira que la convergence par chaîne croissante finie suffit et que l'invocation du théorème est décorative. Deux voies : soit tu **assumes** (« la formalisation sert la reproductibilité, non la difficulté ») et tu déplaces le poids de la contribution vers l'ingénierie ; soit tu **enrichis** le modèle d'impact (treillis non trivial, politiques de propagation qui interagissent, impact quantitatif plutôt que 3 états) pour que les preuves portent quelque chose.

**3. L'échelle.** 11-13 ACI, c'est un exemple didactique. TSE attend des centaines à milliers d'items, des histoires d'exécution longues, idéalement un déploiement. Ta memory indique que tu as construit un pipeline agentique de 29 fichiers pour Databricks — c'est peut-être un candidat de cas réel à projeter.

## Estimation d'effort

Je te donne les deux cibles franchement.

Pour **IEEE Access** (revision du papier actuel) : recadrer la campagne B autour du baseline naïf, exposer les vraies limites du preservation_report au lieu de les lisser, corriger les incohérences formelles (réf `??`, états lifecycle figure/texte), activer ou retirer la vérification par digest. **2 à 4 semaines**, pas de nouvelle expérimentation lourde. Probabilité d'acceptation raisonnable.

Pour **ACM TOSEM ou IEEE TSE** : il faut une campagne empirique nouvelle. Le minimum crédible est (a) + (c) ci-dessus : projection de 3-5 systèmes tiers réels non conçus pour ACM, plus une poignée de cas de rupture documentés. L'étude utilisateur (b) est ce qui ferait vraiment basculer un relecteur, mais c'est le plus coûteux (recrutement, protocole, IRB léger, analyse). Compte **3 à 6 mois** selon que tu inclus ou non l'étude utilisateur, plus une réécriture substantielle des sections 7-9 pour repositionner la contribution comme ingénierie validée empiriquement plutôt que comme théorème. Le taux de rejet de ces venues reste élevé même après ça.

Mon conseil, si tu veux mon avis franc : le papier est *naturellement* un bon papier d'ingénierie de niveau Access ou un solide papier de conférence (ICSE SEIP, ASE). Le pousser vers TSE demande de changer sa nature — passer d'un *reference model qu'on valide par conformité* à une *approche qu'on évalue par confrontation au réel*. C'est faisable, mais c'est un autre papier, pas une révision de celui-ci.

