# Révision du Sprint 1 – Ingestion de données

**Date :** 20/01/2025
**Heure :** 14h00 - 15h30
**Sprint :** 1 (Ingestion de données)

## Participants

| Nom | Rôle | Présent |
|------|------|---------|
| Marie Dupont | Propriétaire de produit | ✓ |
| Jean-Martin | Analyste d'affaires | ✓ |
| Laien Wu | Ingénieur de données | ✓ |
| Sophie Bernard | Analyste de données | ✓ |
| Pierre Durand | Ingénieur DevOps | ✓ |
| Lucas Petit | Maître Scrum | ✓ |

---

## Objectif de sprint

> Mettre en œuvre la collecte automatisée de données à partir de plusieurs sources avec stockage dans l'architecture Data Lake.

**État de l'objectif :** ✅ ATTEINT

---

## Résumé de la démonstration

### 1. Intégration de l'API Binance (Laien)

**Démontré :**
- Récupération de données en direct depuis le point de terminaison Binance `/api/v3/klines`
- Symboles configurables (BTC, ETH, BNB, SOL, ADA)
- Période configurable (90 jours par défaut)
- Logique de nouvelle tentative avec interruption exponentielle
- Limitation de débit conformité

**Commentaires des parties prenantes :**
- Marie : "Pouvons-nous ajouter plus de symboles facilement ?" → Oui, via config.toml
- Jean : "Que se passe-t-il si l'API est en panne ?" → Réessayez 3x, puis échouez avec alert

### 2. Ingestion multi-source (Laien)

**Démontré :**
- Lecture de fichiers CSV (symbols_metadata.csv)
- Chargement de la configuration JSON (portfolio_config.json)
- Web scraping (classements du marché CoinGecko)
- Connexion PostgreSQL (repères historiques)

**5 types de sources implémentés :**
| Source | Statut | Démo |
|--------|--------|------|
| API REST (Binance) | ✅ | Récupération en direct |
| Fichier CSV | ✅ | Métadonnées chargées |
| Fichier JSON | ✅ | Configuration chargée |
| Grattage Web | ✅ | Classements grattés |
| PostgreSQL | ✅ | Benchmarks interrogés |

**Commentaires des parties prenantes :**
- Pierre : "Bonne diversité de sources pour la certification" ✓
- Sophie : "Puis-je voir les données récupérées ?" → Affichage des résultats des classements du marché

### 3. Data Lake Storage (Laien)

**Démontré :**
- Zone Bronze : `data/raw/klines/*.parquet`
- Format Parquet avec application du schéma
- Ingestion incrémentielle (uniquement les nouvelles données)

**Métriques :**
- 5 symboles × 90 jours = 450 enregistrements
- Taille de stockage : ~50 Ko (compressé)
- Temps d'ingestion : ~5 secondes

### 4. Environnement Docker (Pierre)

**Démontré :**
- `docker compose up api` - API en cours d'exécution
- `docker compose --profile pipeline up` – Exécution du pipeline
 – Montages de volumes pour la persistance des données

---

## User Stories terminées

| Identifiant de l'histoire | Titre | Points | Statut |
|----------|-------|--------|--------|
| US-001 | Collecte automatisée des prix | 5 | ✅ Terminé |
| US-002 | Intégration de données multi-sources | 8 | ✅ Terminé |

**Vitesse :** 13 points d'histoire

---

## User Stories non terminées

Aucun - Objectif de sprint entièrement terminé atteint.

---

## Obstacles rencontrés

| Empêchement | Résolution |
|------------|------------|
| La structure de la page CoinGecko a été modifiée | Implémentation de la méthode de scraping de secours |
| Délai d'expiration de la connexion PostgreSQL | Ajout d'une logique de nouvelle tentative de connexion |

---

## Questions et réponses des parties prenantes

**Q (Marie):** La qualité des données est-elle validée ?
**A:** La validation de base (vérifications nulles) est mise en œuvre. Validation complète dans Sprint 2.

**Q (Jean) :** Comment savoir si l'ingestion a échoué ?
**A :** Se connecte actuellement sur la sortie standard. Des alertes seront ajoutées dans Sprint 4.

**Q (Sophie) :** Puis-je interroger les données avec SQL ?
**A :** Oui, l'intégration de DuckDB sera disponible dans Sprint 2.

---

## Actions de l'avis

| Actions | Propriétaire | À payer |
|--------|-------|-----|
| Ajouter une liste de symboles configurables aux documents | Jean | Sprint2 |
| Documenter les codes d'erreur de l'API | Laïen | Sprint2 |
| Approche de suivi du plan | Pierre | Sprint 2 |

---

## Aperçu du Sprint 2

**Objectif :** Mettre en œuvre la transformation des données et l'entrepôt de données DuckDB

**Stories prévues :**
- US-003 : Calculer des mesures financières (5 pts)
- US-007 : API REST pour l'accès aux données (5 pts)
- US-008 : Interface de requête SQL (5 pts)

**Capacité :** 15 points

---

## Actions rétrospectives (à partir de rétros séparées)

| Ce qui s'est bien passé | Ce qu'il faut améliorer |
|----------------|-----------------|
| Implémentation multi-sources en avance sur le calendrier | Besoin de plus de tests unitaires |
| Bonne collaboration entre DE et DevOps | La documentation pourrait être plus détaillée |
| Des exigences claires de la part des entreprises | Démos précédentes des parties prenantes |

---

*Compte-rendu enregistré par : Lucas Petit*
*Sprint accepté par : Marie Dupont (Product Owner)*

