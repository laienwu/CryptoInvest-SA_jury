"""Tests for dbt project structure and configuration."""

from pathlib import Path

import pytest
import yaml

DBT_PROJECT_DIR = Path(__file__).parent.parent / "dbt_project"


class TestDbtProjectStructure:
    def test_dbt_project_yml_exists(self):
        assert (DBT_PROJECT_DIR / "dbt_project.yml").exists()

    def test_profiles_yml_exists(self):
        assert (DBT_PROJECT_DIR / "profiles.yml").exists()

    def test_dbt_project_yml_valid(self):
        content = (DBT_PROJECT_DIR / "dbt_project.yml").read_text()
        config = yaml.safe_load(content)
        assert config["name"] == "portfolio_dbt"
        assert config["config-version"] == 2
        assert config["profile"] == "portfolio"

    def test_profiles_yml_duckdb(self):
        content = (DBT_PROJECT_DIR / "profiles.yml").read_text()
        config = yaml.safe_load(content)
        dev = config["portfolio"]["outputs"]["dev"]
        assert dev["type"] == "duckdb"
        assert "warehouse.duckdb" in dev["path"]

    def test_staging_models_exist(self):
        staging = DBT_PROJECT_DIR / "models" / "staging"
        assert (staging / "stg_klines.sql").exists()
        assert (staging / "stg_symbols.sql").exists()
        assert (staging / "schema.yml").exists()

    def test_marts_models_exist(self):
        marts = DBT_PROJECT_DIR / "models" / "marts"
        assert (marts / "fact_prices.sql").exists()
        assert (marts / "dim_symbol.sql").exists()
        assert (marts / "dim_date.sql").exists()
        assert (marts / "agg_daily_returns.sql").exists()
        assert (marts / "portfolio_summary.sql").exists()
        assert (marts / "schema.yml").exists()

    def test_macros_exist(self):
        assert (DBT_PROJECT_DIR / "macros" / "log_returns.sql").exists()

    def test_custom_tests_exist(self):
        assert (DBT_PROJECT_DIR / "tests" / "assert_positive_volumes.sql").exists()

    def test_staging_schema_has_sources(self):
        content = (DBT_PROJECT_DIR / "models" / "staging" / "schema.yml").read_text()
        config = yaml.safe_load(content)
        assert "sources" in config
        source_names = [s["name"] for s in config["sources"]]
        assert "raw" in source_names

    def test_marts_schema_has_models(self):
        content = (DBT_PROJECT_DIR / "models" / "marts" / "schema.yml").read_text()
        config = yaml.safe_load(content)
        assert "models" in config
        model_names = [m["name"] for m in config["models"]]
        assert "fact_prices" in model_names
        assert "dim_symbol" in model_names
        assert "dim_date" in model_names

    def test_log_return_macro_syntax(self):
        content = (DBT_PROJECT_DIR / "macros" / "log_returns.sql").read_text()
        assert "{% macro log_return" in content
        assert "LN(" in content
