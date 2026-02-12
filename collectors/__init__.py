from .base import BaseCollector
from .clinical_trials import ClinicalTrialsCollector
from .pubmed import PubMedCollector
from .news import NewsCollector
from .patents import PatentsCollector

__all__ = [
    "BaseCollector",
    "ClinicalTrialsCollector",
    "PubMedCollector",
    "NewsCollector",
    "PatentsCollector",
]
