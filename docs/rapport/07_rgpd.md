# Conformité RGPD et Gouvernance (C21)

## 1. Analyse des données traitées

### 1.1 Nature des données

| Type de donnée | Exemple | Personnel ? |
|----------------|---------|-------------|
| Prix OHLCV | BTC: 95000 USD | ❌ Non |
| Volume | 1000 BTC échangés | ❌ Non |
| Timestamp | 2025-01-15 | ❌ Non |
| Symbol | BTCUSDT | ❌ Non |
| Métriques calculées | Rendement: +2% | ❌ Non |

### 1.2 Conclusion
**Aucune donnée personnelle (PII) n'est traitée dans ce projet.**

Les données proviennent de l'API publique Binance et représentent des informations de marché agrégées, anonymes par nature.

---

## 2. Applicabilité du RGPD

### 2.1 Critères d'applicabilité

| Critère RGPD | Applicable ? | Justification |
|--------------|--------------|---------------|
| Données personnelles | ❌ Non | Données de marché uniquement |
| Personnes physiques identifiables | ❌ Non | Données agrégées |
| Traitement automatisé | ✅ Oui | Pipeline ETL |
| Établissement dans l'UE | ✅ Oui | Projet certification FR |

### 2.2 Conclusion
Le RGPD **ne s'applique pas** à ce projet car aucune donnée personnelle n'est collectée, stockée ou traitée.

Cependant, par bonne pratique et anticipation d'évolutions futures, nous documentons les mesures qui seraient nécessaires.

---

## 3. Mesures préventives

### 3.1 Si le projet évoluait vers des données personnelles

**Scénarios futurs possibles :**
- Portefeuilles utilisateurs nominatifs
- Historique de transactions personnelles
- Préférences d'investissement

**Mesures à implémenter :**

| Mesure | Description |
|--------|-------------|
| Registre des traitements | Documenter tous les traitements PII |
| Base légale | Consentement ou intérêt légitime |
| Minimisation | Ne collecter que le nécessaire |
| Durée de conservation | Définir et appliquer des limites |
| Droit d'accès | API pour export données utilisateur |
| Droit à l'effacement | Procédure de suppression |
| Sécurité | Chiffrement, accès restreints |

### 3.2 Architecture privacy-by-design actuelle

Même sans PII, le projet applique des principes de bonne gouvernance :

| Principe | Application |
|----------|-------------|
| Minimisation | Seules les données nécessaires sont stockées |
| Transparence | Sources documentées (Binance public API) |
| Sécurité | Docker isolation, pas d'exposition externe |
| Traçabilité | Logs, Git history |

---

## 4. Registre des traitements (préventif)

### 4.1 Traitement : Collecte données marché

| Champ | Valeur |
|-------|--------|
| **Nom du traitement** | Ingestion données OHLCV |
| **Responsable** | [Votre nom] |
| **Finalité** | Analyse de marché, optimisation portefeuille |
| **Base légale** | N/A (pas de PII) |
| **Catégories de données** | Prix, volumes, timestamps |
| **Destinataires** | Usage interne uniquement |
| **Transferts hors UE** | Oui (API Binance - serveurs globaux) |
| **Durée de conservation** | 1 an |
| **Mesures de sécurité** | Stockage local, Docker |

### 4.2 Traitement : Calcul métriques

| Champ | Valeur |
|-------|--------|
| **Nom du traitement** | Transformation données |
| **Responsable** | [Votre nom] |
| **Finalité** | Calcul rendements, volatilité, corrélations |
| **Données entrée** | OHLCV (pas de PII) |
| **Données sortie** | Métriques agrégées |
| **Durée de conservation** | 1 an |

### 4.3 Traitement : Exposition API

| Champ | Valeur |
|-------|--------|
| **Nom du traitement** | API REST consultation |
| **Responsable** | [Votre nom] |
| **Finalité** | Mise à disposition des résultats |
| **Authentification** | Aucune (MVP) |
| **Logs** | Accès non nominatifs |

---

## 5. Procédures de conformité

### 5.1 Procédure de suppression

```
SI demande de suppression reçue:
    1. Identifier les données concernées
    2. Supprimer de data/raw/
    3. Supprimer de data/processed/
    4. Supprimer de data/output/
    5. Confirmer suppression
FIN
```

**Note** : Non applicable actuellement (pas de PII).

### 5.2 Procédure d'export (droit d'accès)

```
SI demande d'export reçue:
    1. Identifier les données utilisateur
    2. Générer export JSON
    3. Transmettre de manière sécurisée
FIN
```

**Note** : Non applicable actuellement (pas de PII).

### 5.3 Purge automatique

| Zone | Rétention | Fréquence purge |
|------|-----------|-----------------|
| data/raw/ | 1 an | Mensuelle |
| data/processed/ | 1 an | Mensuelle |
| data/output/ | 30 jours | Hebdomadaire |

Script de purge (à implémenter si nécessaire) :
```python
# Exemple de purge des fichiers > 1 an
from pathlib import Path
from datetime import datetime, timedelta

def purge_old_files(directory: Path, max_age_days: int = 365):
    cutoff = datetime.now() - timedelta(days=max_age_days)
    for file in directory.glob("**/*"):
        if file.is_file() and file.stat().st_mtime < cutoff.timestamp():
            file.unlink()
```

---

## 6. Sécurité des données

### 6.1 Mesures techniques

| Mesure | Implémentation |
|--------|----------------|
| Isolation | Docker containers |
| Accès réseau | Port 8000 local uniquement |
| Chiffrement transit | HTTPS vers Binance |
| Chiffrement repos | Non (données publiques) |
| Backup | Volume Docker persistant |

### 6.2 Mesures organisationnelles

| Mesure | Implémentation |
|--------|----------------|
| Accès limités | Développeur unique |
| Documentation | Ce rapport |
| Sensibilisation | N/A (équipe de 1) |

---

## 7. Conclusion

### 7.1 Synthèse conformité

| Aspect | Status |
|--------|--------|
| Données personnelles | ❌ Aucune |
| RGPD applicable | ❌ Non |
| Bonnes pratiques | ✅ Appliquées |
| Documentation | ✅ Complète |
| Évolutivité | ✅ Mesures préventives documentées |

### 7.2 Recommandations futures

Si le projet évolue vers le traitement de données personnelles :
1. Mettre à jour ce registre
2. Implémenter les procédures documentées
3. Ajouter authentification à l'API
4. Chiffrer les données au repos
5. Nommer un DPO si nécessaire
