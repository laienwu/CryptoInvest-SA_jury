# Communication Projet (C7)

## 1. Stratégie de communication

### 1.1 Objectifs
- Informer les parties prenantes de l'avancement
- Démontrer les réalisations techniques
- Préparer la validation finale (jury)

### 1.2 Plan de communication

| Étape | Cible | Message | Support | Date |
|-------|-------|---------|---------|------|
| Lancement | Jury/Formateur | Présentation projet | Oral | S1 |
| Jalon 1 | Formateur | Pipeline fonctionnel | Démo | S2 |
| Jalon 2 | Formateur | Métriques OK | Démo | S4 |
| Jalon 3 | Formateur | DWH opérationnel | Démo | S6 |
| Jalon 4 | Formateur | API déployée | Démo | S8 |
| Livraison | Jury | Projet complet | Rapport | S12 |
| Soutenance | Jury | Validation | Oral | S12 |

---

## 2. Supports de communication

### 2.1 Documentation technique

**README.md** (utilisateurs) :
```markdown
# Portfolio Optimization

## Quick Start
docker compose up

## API
http://localhost:8000/docs

## Pipeline
docker compose --profile pipeline run pipeline
```

**CLAUDE.md** (développeurs) :
- Architecture
- Décisions techniques
- Roadmap certification

### 2.2 Documentation API (auto-générée)

Accessible sur `/docs` (Swagger UI) :
- Liste des endpoints
- Paramètres et réponses
- Try it out interactif

### 2.3 Rapport professionnel

Structure :
1. Analyse du besoin (C1)
2. Cartographie des données (C2)
3. Cadre technique (C3)
4. Veille (C4)
5. Planification (C5, C6)
6. Communication (C7)
7. Conformité RGPD (C21)

---

## 3. Accessibilité des supports

### 3.1 Critères respectés
Conformément aux recommandations [RGAA](https://accessibilite.numerique.gouv.fr/) :

| Critère | Application |
|---------|-------------|
| Structuration | Titres hiérarchiques (H1, H2...) |
| Contraste | Texte noir sur fond blanc |
| Alternative texte | Diagrammes ASCII (pas d'images) |
| Navigation | Table des matières |
| Format | Markdown (texte brut) |

### 3.2 Formats de diffusion
| Support | Format | Accessibilité |
|---------|--------|---------------|
| Rapport | Markdown/PDF | ✅ Texte structuré |
| Slides | PDF | ✅ Export accessible |
| Code | Python | ✅ Commentaires |
| API doc | HTML (Swagger) | ✅ Standard |

---

## 4. Soutenance

### 4.1 Structure présentation (30 min)

| Partie | Durée | Contenu |
|--------|-------|---------|
| Introduction | 3 min | Contexte, besoin |
| Architecture | 5 min | Data Lake, DWH, ETL |
| Démonstration | 10 min | Pipeline + API live |
| Choix techniques | 5 min | Justifications |
| Conformité | 3 min | RGPD, éco-conception |
| Conclusion | 2 min | Bilan, perspectives |
| Questions | 10 min | Échanges jury |

### 4.2 Points clés à démontrer

| Compétence | Démonstration |
|------------|---------------|
| C8 (Extraction) | `python -m src.pipeline.ingest` |
| C9 (SQL) | Requêtes DuckDB live |
| C12 (API) | Swagger UI /docs |
| C13 (Star schema) | `fact_prices`, `dim_*` |
| C14 (DWH) | `get_storage("duckdb")` |
| C18/C19 (Infra) | `docker compose up` |

### 4.3 Anticipation questions jury

| Question probable | Réponse préparée |
|-------------------|------------------|
| Pourquoi DuckDB vs Postgres ? | Léger, SQL sur fichiers, pas de serveur |
| Comment scale le système ? | Storage pluggable, ajout backend |
| RGPD sur données crypto ? | Données publiques, pas de PII |
| Limites du projet ? | Pas de streaming, pas de ML |

---

## 5. Retours et amélioration continue

### 5.1 Collecte des retours
| Source | Méthode | Fréquence |
|--------|---------|-----------|
| Formateur | Points hebdo | Hebdo |
| Auto-évaluation | Rétrospective | Fin de phase |
| Jury | Soutenance | Finale |

### 5.2 Intégration des retours
- Retours documentés dans Git (issues/commits)
- Améliorations priorisées dans backlog
- Rapport mis à jour itérativement

---

## 6. Livrables finaux

### 6.1 Checklist livraison

| Livrable | Format | Status |
|----------|--------|--------|
| Code source | Git repo | ✅ |
| README | Markdown | ✅ |
| Documentation technique | Markdown | ✅ |
| Rapport professionnel | Markdown/PDF | ✅ |
| Slides soutenance | PDF/Markdown | ✅ |
| Démo fonctionnelle | Docker | ✅ |

### 6.2 Arborescence finale

```
binance/
├── src/                    # Code source
├── data/                   # Données (volume Docker)
├── docs/
│   └── rapport/            # Rapport certification
│       ├── 01_analyse_besoin.md
│       ├── 02_cartographie_donnees.md
│       ├── 03_cadre_technique.md
│       ├── 04_veille.md
│       ├── 05_planification.md
│       ├── 06_communication.md
│       ├── 07_rgpd.md
│       ├── 08_scd_dimensions.md
│       ├── 09_catalogue_donnees.md
│       ├── 10_merise.md
│       ├── slides_soutenance.md
│       ├── demo_guide.md
│       └── questions_jury.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── CLAUDE.md
└── README.md
```
