# Communication Projet (C7)

## 1. Strategie de communication

### 1.1 Objectifs

- Informer les parties prenantes de l'avancement du projet
- Demonstrer les realisations techniques a chaque jalon
- Justifier les choix techniques et organisationnels tout au long du projet
- Integrer les retours des parties prenantes dans le processus iteratif
- Preparer la validation finale (jury de certification)

### 1.2 Plan de communication

| Etape | Cible | Message | Support | Date |
|-------|-------|---------|---------|------|
| Lancement | Jury / Formateur | Presentation projet, perimetre | Oral + slides | S1 |
| Jalon 1 | Formateur + PO | Pipeline ingest fonctionnel (6 sources) | Demo live | S2 |
| Jalon 2 | Formateur | Metriques calculees (PyArrow) | Demo + rapport | S4 |
| Jalon 3 | Equipe | DWH + dbt operationnel | Sprint review | S6 |
| Jalon 4 | Formateur + PO | API 46 endpoints + dashboard 32 pages | Demo live | S9 |
| Jalon 5 | Equipe | 6 strategies d'optimisation | Sprint review | S12 |
| Jalon 6 | Formateur | Streaming Kafka operationnel | Demo live | S14 |
| Jalon 7 | DevOps | Monitoring Prometheus + Grafana | Dashboard Grafana | S16 |
| Livraison | Jury | Projet complet | Rapport + code | S18 |
| Soutenance | Jury | Validation finale | Oral 1h30 | S18 |

### 1.3 Justification des choix

Tout au long du projet, les choix techniques et organisationnels sont justifies et documentes :

| Type de choix | Justification | Document |
|---------------|---------------|----------|
| Choix techniques | Architecture Decision Records (ADR) | `docs/architecture/adr/` (7 ADR) |
| Choix organisationnels | Methodologie Agile, Scrum | `docs/rapport/05_planification.md` |
| Choix de planning | Chemin critique, estimation collective | `docs/rapport/05_planification.md` |
| Choix de gouvernance | Conformite RGPD, catalogue | `docs/rapport/07_rgpd.md`, `docs/rapport/09_catalogue_donnees.md` |

---

## 2. Supports de communication

### 2.1 Documentation technique

**README.md** (utilisateurs) :
- Quick start avec Docker Compose
- Documentation des profils (streaming, monitoring, airflow, full)
- Liens vers l'API et le dashboard

**Documentation de maintenance** (developpeurs / mainteneur) :
- Architecture complete du systeme
- Patterns a respecter (Storage ABC, PipelineConfig, Depends injection)
- Commandes rapides
- Script de demonstration

### 2.2 Documentation API (auto-generee)

Accessible sur `/docs` (Swagger UI) et `/redoc` (ReDoc) :
- 46 endpoints documentes
- Schemas Pydantic (entrees / sorties)
- Try it out interactif
- Specification OpenAPI 3.0 (`docs/architecture/api_specification.yaml`)

### 2.3 Documentation operationnelle

| Document | Contenu | Destinataire |
|----------|---------|--------------|
| Runbook | Procedures operationnelles | DevOps |
| Monitoring | Metriques et alertes | DevOps |
| SLA | Niveaux de service | PO / Client |
| Securite | Checklist de securite | DevOps |
| Incident response | Gestion des incidents | Equipe |

---

## 3. Accessibilite des supports (RGAA)

### 3.1 Criteres respectes

Conformement au Referentiel General d'Amelioration de l'Accessibilite (RGAA) :

| Critere RGAA | Application dans le projet |
|--------------|----------------------------|
| Structuration semantique | Titres hierarchiques (H1, H2, H3) dans tous les documents |
| Contraste | Texte noir sur fond blanc (ratio > 4.5:1) |
| Alternative textuelle | Diagrammes en ASCII art, pas d'images sans attribut alt |
| Navigation | Table des matieres, liens internes |
| Format | Markdown (texte brut structure), exportable en PDF accessible |
| Langue | Documents en francais, langue declaree dans les exports HTML |
| Tableaux | En-tetes de colonnes identifies dans tous les tableaux |
| Slides soutenance | HTML avec structure semantique, contraste respecte (bleu fonce / or) |
| Dashboard Streamlit | Interface web standard, navigation par onglets |
| API documentation | Swagger UI / ReDoc = standards accessibles |

### 3.2 Formats de diffusion

| Support | Format | Accessibilite |
|---------|--------|---------------|
| Rapport | Markdown / PDF | Texte structure, lecteur d'ecran compatible |
| Code source | Python | Commentaires, docstrings |
| API documentation | HTML (Swagger UI) | Standard OpenAPI |
| Dashboard | Streamlit (web) | Interface standard, labels |
| Grafana dashboards | Web | Interface standard |

---
**Epreuves evaluees :**
- E1 : Collecte, stockage, mise a disposition (C8-C12)
- E2 : Data Warehouse (C13-C17)
- E3 : Data Lake (C18-C21)

## 4. Retours des parties prenantes

### 4.1 Processus de collecte des retours

| Source | Methode | Frequence | Documentation |
|--------|---------|-----------|---------------|
| Product Owner (Marie Dupont) | Sprint review + validation fonctionnelle | Bi-mensuelle | `docs/business/meeting_notes/` |
| Formateur | Points hebdomadaires | Hebdomadaire | Notes de reunion |
| Business Analyst (Jean-Martin) | Revue de documentation | Par phase | Commentaires sur PR |
| Data Analyst (Sophie Bernard) | Validation des calculs financiers | Par module | Tests de non-regression |
| Jury | Soutenance finale | Unique | Grille d'evaluation |

### 4.2 Integration des retours

Le processus d'integration des retours suit un cycle structure :

1. **Collecte** : retours documentes lors des sprint reviews et points hebdomadaires
2. **Priorisation** : classement par impact (bloquant / important / mineur) avec le PO
3. **Planification** : integration dans le sprint suivant (backlog)
4. **Implementation** : developpement + tests
5. **Validation** : demonstration au demandeur lors du sprint review suivant
6. **Documentation** : mise a jour du rapport et des artefacts impactes

### 4.3 Exemples de retours integres

| Retour | Source | Action | Sprint |
|--------|--------|--------|--------|
| Ajouter des actifs traditionnels | PO | Integration yfinance (actions, ETF, matieres premieres) | S4 |
| Comparer les strategies | PO | Page Strategy Showdown (6 optimiseurs cote a cote) | S12 |
| Documenter la gouvernance | Formateur | Rapport RGPD + catalogue de donnees | S6 |
| Valider les calculs de Sharpe | Data Analyst | Tests unitaires specifiques, annualisation verifiee | S5 |
| Monitoring en production | DevOps | Prometheus + Grafana + alertes | S15 |


