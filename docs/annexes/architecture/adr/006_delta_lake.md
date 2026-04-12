# ADR-006 : Delta Lake pour un Data Lake ACID

## Statut
Accepte

## Contexte
Le data lake stocke les donnees brutes, traitees et de sortie dans des fichiers Parquet simples. Bien que Parquet fournisse un stockage colonnaire efficace, il lui manque :
- **Transactions ACID** : des ecritures concurrentes peuvent corrompre les donnees
- **Time travel** : aucune possibilite d'interroger des instantanes historiques
- **Schema enforcement** : aucune garantie integree sur l'evolution du schema
- **Operations atomiques** : des ecritures partielles peuvent laisser un etat incoherent

Pour une plateforme de data engineering de niveau production gerant une ingestion a haute frequence (bougies 1 minute, flux de carnet d'ordres), ces garanties deviennent critiques.

## Decision
Ajouter **Delta Lake** comme backend de stockage optionnel via le package Python `deltalake` (delta-rs), une implementation en Rust pur ne necessitant pas de JVM.

### Choix de conception cles :
1. **Dependance optionnelle** : Delta Lake coexiste avec le backend Parquet simple. Les utilisateurs choisissent via la configuration `storage_backend`.
2. **Meme Storage ABC** : `DeltaStorage` implemente l'interface `Storage` existante, sans modification d'API.
3. **delta-rs (sans JVM)** : le package `deltalake`, base sur Rust, fournit la prise en charge du protocole Delta Lake sans dependance Java/Spark.
4. **Partitionnement par symbole** : les donnees brutes sont partitionnees par `symbol` pour des requetes efficaces par actif.

## Consequences

### Positives
- Les transactions ACID evitent la corruption des donnees lors d'executions concurrentes du pipeline
- Le time travel facilite l'audit et le debogage des problemes de qualite des donnees
- Le schema enforcement detecte les derives de schema au moment de l'ecriture
- L'integration est fluide via le pattern de fabrique Storage ABC deja en place

### Negatives
- Dependance optionnelle supplementaire (`deltalake`)
- Latence d'ecriture legerement plus elevee due a la gestion du journal de transactions
- Les metadonnees Delta Lake (`_delta_log/`) ajoutent un surcout de stockage

### Neutres
- Parquet simple reste le backend par defaut ; Delta Lake est active sur option
- Aucun changement n'est requis dans le code du pipeline, l'interface `Storage` restant identique
