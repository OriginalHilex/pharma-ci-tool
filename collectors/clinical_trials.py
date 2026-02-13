from typing import Any
import logging
from .base import BaseCollector
from config import settings
from config.search_config import AssetConfig, DiseaseConfig

logger = logging.getLogger(__name__)


class ClinicalTrialsCollector(BaseCollector):
    """Collector for ClinicalTrials.gov API v2."""

    def __init__(self):
        super().__init__()
        self.base_url = settings.clinicaltrials_api_url

    def get_source_name(self) -> str:
        return "ClinicalTrials.gov"

    def collect(self, query: str, **kwargs) -> list[dict[str, Any]]:
        """
        Collect clinical trials matching the query.

        Args:
            query: Drug name or condition to search for
            **kwargs:
                - max_results: Maximum number of results (default 100)
                - status: Filter by trial status
                - extra_params: Additional API params to merge

        Returns:
            List of clinical trial records
        """
        max_results = kwargs.get("max_results", 100)
        status_filter = kwargs.get("status")
        extra_params = kwargs.get("extra_params", {})

        trials = []
        page_token = None

        while len(trials) < max_results:
            params = {
                "query.term": query,
                "pageSize": min(50, max_results - len(trials)),
                "fields": ",".join([
                    "NCTId",
                    "BriefTitle",
                    "OfficialTitle",
                    "OverallStatus",
                    "Phase",
                    "StartDate",
                    "PrimaryCompletionDate",
                    "CompletionDate",
                    "EnrollmentCount",
                    "LeadSponsorName",
                    "Condition",
                    "InterventionName",
                    "PrimaryOutcomeMeasure",
                    "BriefSummary",
                    "LastUpdatePostDate",
                ]),
            }

            # Merge any extra params (query.intr, query.cond, filter.overallStatus, etc.)
            params.update(extra_params)

            if page_token:
                params["pageToken"] = page_token
            if status_filter:
                params["filter.overallStatus"] = status_filter

            try:
                response = self._make_request(
                    f"{self.base_url}/studies",
                    params=params,
                )
                data = response.json()
            except Exception as e:
                logger.error(f"Error fetching trials for '{query}': {e}")
                break

            studies = data.get("studies", [])
            if not studies:
                break

            for study in studies:
                trial = self._parse_study(study)
                if trial:
                    trials.append(trial)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        logger.info(f"Collected {len(trials)} trials for query: {query}")
        return trials

    def collect_by_asset(self, asset: AssetConfig, **kwargs) -> list[dict[str, Any]]:
        """
        Asset-specific monitoring (indication-agnostic).

        Searches the intervention field with all aliases OR'd together,
        capturing any trial where this drug appears regardless of disease.
        """
        or_query = asset.or_query()
        extra_params = {"query.intr": or_query}
        return self._collect_with_params(extra_params, **kwargs)

    def collect_by_disease(self, disease: DiseaseConfig, **kwargs) -> list[dict[str, Any]]:
        """
        Disease discovery monitoring (interventional only).

        Searches the condition field with all disease aliases,
        filtered to interventional studies only.
        """
        or_query = disease.or_query()
        extra_params = {
            "query.cond": or_query,
            "filter.overallStatus": "RECRUITING,ACTIVE_NOT_RECRUITING,ENROLLING_BY_INVITATION,NOT_YET_RECRUITING,COMPLETED",
        }
        return self._collect_with_params(extra_params, **kwargs)

    def _collect_with_params(self, extra_params: dict, **kwargs) -> list[dict[str, Any]]:
        """Run collection with extra API parameters, bypassing query.term."""
        max_results = kwargs.get("max_results", 100)
        status_filter = kwargs.get("status")

        trials = []
        page_token = None

        while len(trials) < max_results:
            params = {
                "pageSize": min(50, max_results - len(trials)),
                "fields": ",".join([
                    "NCTId",
                    "BriefTitle",
                    "OfficialTitle",
                    "OverallStatus",
                    "Phase",
                    "StartDate",
                    "PrimaryCompletionDate",
                    "CompletionDate",
                    "EnrollmentCount",
                    "LeadSponsorName",
                    "Condition",
                    "InterventionName",
                    "PrimaryOutcomeMeasure",
                    "BriefSummary",
                    "LastUpdatePostDate",
                ]),
            }

            params.update(extra_params)

            if page_token:
                params["pageToken"] = page_token
            if status_filter:
                params["filter.overallStatus"] = status_filter

            try:
                response = self._make_request(
                    f"{self.base_url}/studies",
                    params=params,
                )
                data = response.json()
            except Exception as e:
                logger.error(f"Error fetching trials: {e}")
                break

            studies = data.get("studies", [])
            if not studies:
                break

            for study in studies:
                trial = self._parse_study(study)
                if trial:
                    trials.append(trial)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        logger.info(f"Collected {len(trials)} trials")
        return trials

    def _parse_study(self, study: dict) -> dict[str, Any] | None:
        """Parse a study record from the API response."""
        try:
            protocol = study.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})
            status_module = protocol.get("statusModule", {})
            design_module = protocol.get("designModule", {})
            sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
            conditions_module = protocol.get("conditionsModule", {})
            interventions_module = protocol.get("armsInterventionsModule", {})
            outcomes_module = protocol.get("outcomesModule", {})
            description_module = protocol.get("descriptionModule", {})

            nct_id = id_module.get("nctId")
            if not nct_id:
                return None

            # Extract phases (can be a list)
            phases = design_module.get("phases", [])
            phase = phases[0] if phases else None

            # Extract primary outcomes
            primary_outcomes = outcomes_module.get("primaryOutcomes", [])
            primary_endpoint = None
            if primary_outcomes:
                primary_endpoint = primary_outcomes[0].get("measure")

            # Extract interventions
            interventions = interventions_module.get("interventions", [])
            intervention_names = [i.get("name", "") for i in interventions]

            # Extract last update date
            last_update_struct = status_module.get("lastUpdatePostDateStruct", {})
            last_updated = self._parse_date(last_update_struct.get("date"))

            return {
                "nct_id": nct_id,
                "title": id_module.get("briefTitle") or id_module.get("officialTitle", ""),
                "status": status_module.get("overallStatus"),
                "phase": phase,
                "start_date": self._parse_date(
                    status_module.get("startDateStruct", {}).get("date")
                ),
                "completion_date": self._parse_date(
                    status_module.get("completionDateStruct", {}).get("date")
                ),
                "enrollment": design_module.get("enrollmentInfo", {}).get("count"),
                "sponsor": sponsor_module.get("leadSponsor", {}).get("name"),
                "conditions": conditions_module.get("conditions", []),
                "interventions": intervention_names,
                "primary_endpoint": primary_endpoint,
                "summary": description_module.get("briefSummary"),
                "source_url": f"https://clinicaltrials.gov/study/{nct_id}",
                "last_updated": last_updated,
                "raw_data": study,
            }
        except Exception as e:
            logger.error(f"Error parsing study: {e}")
            return None

    def collect_by_indication(self, indication: str, **kwargs) -> list[dict[str, Any]]:
        """Collect all trials for a specific indication (legacy method)."""
        return self.collect(indication, **kwargs)

    def collect_by_drug(self, drug_name: str, **kwargs) -> list[dict[str, Any]]:
        """Collect trials for a specific drug/intervention (legacy method)."""
        return self.collect(drug_name, **kwargs)
