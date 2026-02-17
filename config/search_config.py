"""Loader for centralized search configuration (search_config.yaml)."""

from dataclasses import dataclass, field
from pathlib import Path
from functools import lru_cache
import yaml


def _or_query(terms: list[str], quote: bool = True) -> str:
    """Build an OR query string from a list of terms."""
    parts = []
    for term in terms:
        if quote and " " in term:
            parts.append(f'"{term}"')
        else:
            parts.append(term)
    return " OR ".join(parts)


@dataclass
class IndicationConfig:
    """An indication linked to a specific asset."""
    name: str
    aliases: list[str] = field(default_factory=list)

    def or_query(self, quote: bool = True) -> str:
        """Build an OR query string from aliases."""
        return _or_query(self.aliases, quote)


@dataclass
class AssetConfig:
    """A tracked drug asset with all searchable aliases."""
    name: str
    aliases: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    indications: list[IndicationConfig] = field(default_factory=list)

    def or_query(self, quote: bool = True) -> str:
        """Build an OR query string from drug aliases only."""
        return _or_query(self.aliases, quote)

    def target_or_query(self, quote: bool = True) -> str:
        """Build an OR query string from target aliases."""
        return _or_query(self.targets, quote)


@dataclass
class DiseaseConfig:
    """A tracked disease/indication with all searchable aliases."""
    name: str
    aliases: list[str] = field(default_factory=list)

    def or_query(self, quote: bool = True) -> str:
        """Build an OR query string from aliases."""
        return _or_query(self.aliases, quote)


@dataclass
class SearchConfig:
    """Full search configuration loaded from YAML."""
    assets: list[AssetConfig] = field(default_factory=list)
    diseases: list[DiseaseConfig] = field(default_factory=list)
    intervention_keywords: list[str] = field(default_factory=list)
    news_discovery_keywords: list[str] = field(default_factory=list)
    patent_recent_days: int = 365
    patent_relevance_keywords: list[str] = field(default_factory=list)
    patent_noise_keywords: list[str] = field(default_factory=list)

    def intervention_or_query(self, quote: bool = True) -> str:
        """Build OR query from intervention keywords."""
        return _or_query(self.intervention_keywords, quote)

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

    assets = []
    for a in raw.get("assets", []):
        indications = [
            IndicationConfig(name=ind["name"], aliases=ind.get("aliases", []))
            for ind in a.get("indications", [])
        ]
        assets.append(AssetConfig(
            name=a["name"],
            aliases=a.get("aliases", []),
            targets=a.get("targets", []),
            indications=indications,
        ))

    diseases = [
        DiseaseConfig(name=d["name"], aliases=d.get("aliases", []))
        for d in raw.get("diseases", [])
    ]

    patent_settings = raw.get("patent_settings", {})

    return SearchConfig(
        assets=assets,
        diseases=diseases,
        intervention_keywords=raw.get("intervention_keywords", []),
        news_discovery_keywords=raw.get("news_discovery_keywords", []),
        patent_recent_days=patent_settings.get("recent_days", 365),
        patent_relevance_keywords=patent_settings.get("relevance_keywords", []),
        patent_noise_keywords=patent_settings.get("noise_keywords", []),
    )


@lru_cache
def get_search_config() -> SearchConfig:
    """Get cached search configuration instance."""
    return load_search_config()
