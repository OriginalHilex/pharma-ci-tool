"""Loader for centralized search configuration (search_config.yaml)."""

from dataclasses import dataclass, field
from pathlib import Path
from functools import lru_cache
import yaml


@dataclass
class AssetConfig:
    """A tracked drug asset with all searchable aliases."""
    name: str
    aliases: list[str] = field(default_factory=list)

    def or_query(self, quote: bool = True) -> str:
        """Build an OR query string from aliases.

        Args:
            quote: Wrap multi-word aliases in double quotes.
        """
        terms = []
        for alias in self.aliases:
            if quote and " " in alias:
                terms.append(f'"{alias}"')
            else:
                terms.append(alias)
        return " OR ".join(terms)


@dataclass
class DiseaseConfig:
    """A tracked disease/indication with all searchable aliases."""
    name: str
    aliases: list[str] = field(default_factory=list)

    def or_query(self, quote: bool = True) -> str:
        """Build an OR query string from aliases."""
        terms = []
        for alias in self.aliases:
            if quote and " " in alias:
                terms.append(f'"{alias}"')
            else:
                terms.append(alias)
        return " OR ".join(terms)


@dataclass
class SearchConfig:
    """Full search configuration loaded from YAML."""
    assets: list[AssetConfig] = field(default_factory=list)
    diseases: list[DiseaseConfig] = field(default_factory=list)
    intervention_keywords: list[str] = field(default_factory=list)
    news_discovery_keywords: list[str] = field(default_factory=list)

    def intervention_or_query(self, quote: bool = True) -> str:
        """Build OR query from intervention keywords."""
        terms = []
        for kw in self.intervention_keywords:
            if quote and " " in kw:
                terms.append(f'"{kw}"')
            else:
                terms.append(kw)
        return " OR ".join(terms)

    def news_keywords_or_query(self) -> str:
        """Build OR query from news discovery keywords."""
        return " OR ".join(self.news_discovery_keywords)


def load_search_config(config_path: str | Path | None = None) -> SearchConfig:
    """Load search configuration from YAML file.

    Args:
        config_path: Path to YAML file. Defaults to config/search_config.yaml
                     relative to this file.
    """
    if config_path is None:
        config_path = Path(__file__).parent / "search_config.yaml"
    else:
        config_path = Path(config_path)

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    assets = [
        AssetConfig(name=a["name"], aliases=a.get("aliases", []))
        for a in raw.get("assets", [])
    ]
    diseases = [
        DiseaseConfig(name=d["name"], aliases=d.get("aliases", []))
        for d in raw.get("diseases", [])
    ]

    return SearchConfig(
        assets=assets,
        diseases=diseases,
        intervention_keywords=raw.get("intervention_keywords", []),
        news_discovery_keywords=raw.get("news_discovery_keywords", []),
    )


@lru_cache
def get_search_config() -> SearchConfig:
    """Get cached search configuration instance."""
    return load_search_config()
