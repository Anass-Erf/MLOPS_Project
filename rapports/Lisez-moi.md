# Rapport académique — Prédiction du stress hydrique des cultures

Rapport français de **38 pages**, dont 12 chapitres et les annexes A à J, fondé sur le dépôt au commit `0f3bc509191d5ec178bd94abd7edfc58289e38e5`.

- [Document Word modifiable](Rapport_Academique_MLOps_DataOps_Stress_Hydrique_Final.docx)
- [Version PDF](Rapport_Academique_MLOps_DataOps_Stress_Hydrique_Final.pdf)

La couverture contient exactement sept emplacements de noms et un emplacement de logo. Le DOCX contient une table des matières dynamique et deux listes automatiques, déjà actualisées. Après modification dans Microsoft Word : `Ctrl+A`, puis `F9`. La pagination peut varier légèrement selon les polices et le logiciel utilisés.

## Chapitres

- Chapitre 1 — Contexte et problématique
- Chapitre 2 — Gestion Agile et collaboration
- Chapitre 3 — Données et DataOps
- Chapitre 4 — Qualité, Data Contract et lineage
- Chapitre 5 — Exploration et feature engineering
- Chapitre 6 — Modélisation Machine Learning
- Chapitre 7 — MLOps et MLflow
- Chapitre 8 — API, interface et serving
- Chapitre 9 — Conteneurisation et déploiement
- Chapitre 10 — Intégration continue
- Chapitre 11 — Monitoring et observabilité
- Chapitre 12 — Résultats, limites et discussion

L’introduction générale, la conclusion, la bibliographie et dix annexes complètent ces chapitres.

## Figures incluses

1. Graphe des assets Dagster et séparation de l’entraînement explicite.
2. Architecture intégrée : chemin DataOps, apprentissage et services.
3. Traçabilité des données, du fichier source à l’événement de prédiction.
4. Distributions des variables et du proxy sur l’ensemble d’apprentissage.
5. Évolution du proxy pendant les saisons d’apprentissage, par site.
6. Matrice des corrélations de Pearson sur l’apprentissage.
7. Comparaison des RMSE de validation des quatre modèles.
8. Prédictions du modèle figé comparées au proxy sur le test.
9. Capture existante du suivi d’expériences MLflow.
10. Documentation Swagger des endpoints réels.
11. Mode Automatic Weather avec instantané NASA vérifié en cache.
12. Affichage de la prévision dans l’interface Streamlit.
13. Services Docker Compose et séparation du Dagster local.

## Tableaux inclus

1. Périmètre scientifique et fonctionnel.
2. Product Backlog reconstitué à partir des fonctionnalités.
3. Trois sprints pédagogiques et éléments de revue.
4. Sites et hypothèses de sol.
5. Variables météorologiques du schéma réel.
6. Relations et responsabilités du stockage analytique.
7. Règles numériques reprises du contrat existant.
8. Couverture des contrôles automatisés.
9. Familles de variables effectivement utilisées.
10. Partitions réellement présentes après filtrage saisonnier.
11. Hyperparamètres principaux de l’expérience.
12. Comparaison réelle des modèles sur la validation.
13. Résultats sur les 1 074 observations de test.
14. Performance du modèle sélectionné par site.
15. Métadonnées de la version de production.
16. Endpoints et comportements de l’API.
17. Services Compose, ports par défaut et persistance.
18. Étapes réelles des workflows CI.
19. Exécutions GitHub Actions du commit final audité.
20. Indicateurs et seuils de monitoring configurés.
21. Lecture des rapports de monitoring présents dans le dépôt.
22. Limites, conséquences et pistes d’amélioration.
23. Emplacements et responsabilités du dépôt.
24. Champs de la réponse de prédiction.
25. Commandes du Makefile et effets à connaître.
26. Contrat structurel, temporel et de provenance.
27. Dépendances et effets des assets.
28. Matrice finale de conformité aux exigences du module.

Une liste des abréviations non numérotée figure également dans les pages liminaires.

## Limites et éléments non établis

- Les trois sprints, les User Stories et les revues sont une reconstruction pédagogique explicitement signalée. Les cérémonies réellement tenues et la répartition individuelle des tâches ne sont pas documentées.
- Aucune Pull Request n’a été renvoyée par l’API GitHub consultée le 17 septembre 2026. La procédure écrite ne constitue pas une preuve de revue effective.
- La procédure Komodo existe ; l’état actuel du déploiement distant et une capture Komodo ne sont pas vérifiables dans les éléments disponibles.
- La cible est un proxy simulé de stress, sans mesures indépendantes au champ. Le modèle concerne le blé, trois sites, un horizon du lendemain et une fenêtre météorologique de 30 jours.
- La persistance obtient une meilleure performance que le modèle sélectionné sur le test ; elle dispose toutefois d’un état hydrique simulé fondé sur un historique plus long. Cette comparaison est discutée sans revendiquer une supériorité du ML.
- Le monitoring en production ne permet pas de mesurer la performance sans labels ; le rapport live ne contient qu’une prédiction, sous le minimum de 30 observations requis pour l’analyse de dérive.
- Les workflows réalisent la CI ; ils ne réalisent ni déploiement continu ni construction Docker. Dagster est exécuté localement, hors des trois services Compose.

## Vérifications et sources de rédaction

Les 156 fichiers préexistants suivis au début de l’audit sont inchangés. Les opérations de rédaction n’ont pas relancé l’entraînement ni remplacé les artefacts applicatifs.

- [Contrôle final](sources/controle_final.json)
- [Matrice de vérification](sources/matrice_audit.md)
- [Vérification distante GitHub](sources/verification_github.json)
- [Source du rapport](sources/rapport.md)
- [Générateur DOCX](sources/generer_rapport.py)
- [Générateur des schémas](sources/generer_diagrammes.py)

Les schémas représentent le code inspecté ; les graphiques et captures d’interface proviennent du dépôt. Aucun écran DataOps fictif n’a été ajouté. Les résultats de tests relatés sont ceux des preuves conservées et des exécutions CI consultées, pas une nouvelle campagne de tests réalisée pour rédiger le rapport.
