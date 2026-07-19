from __future__ import annotations

from dataclasses import dataclass

from app.config import ETLSystem, Settings
from app.etl.extract import ExtractService
from app.etl.load import LoadService
from app.etl.transform import TransformService


@dataclass
class ETLSystemResult:
    system: str
    extracted_records: int
    transformed_documents: int
    loaded_documents: int


class ETLPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.extract_service = ExtractService(
            timeout=settings.etl_request_timeout_seconds,
            use_secret_manager=settings.etl_secret_manager_enabled,
            use_mock=settings.etl_mock_mode,
            project_id=settings.etl_secret_manager_project_id,
        )
        self.transform_service = TransformService()
        self.load_service = LoadService(settings=settings)

    async def run(self, systems: list[str] | None = None, dry_run: bool = False) -> list[ETLSystemResult]:
        selected = self._select_systems(systems)
        results: list[ETLSystemResult] = []

        for system in selected:
            extracted = await self.extract_service.run(system)
            transformed = self.transform_service.run(extracted)
            loaded_count = await self.load_service.run(transformed, dry_run=dry_run)
            results.append(
                ETLSystemResult(
                    system=system.name,
                    extracted_records=len(extracted.records),
                    transformed_documents=len(transformed.documents),
                    loaded_documents=loaded_count,
                )
            )

        return results

    def _select_systems(self, systems: list[str] | None) -> list[ETLSystem]:
        if not self.settings.etl_systems:
            return []

        if not systems:
            return self.settings.etl_systems

        requested = {item.strip().lower() for item in systems if item.strip()}
        selected = [system for system in self.settings.etl_systems if system.name.lower() in requested]
        if len(selected) != len(requested):
            known = {system.name.lower() for system in self.settings.etl_systems}
            unknown = sorted(requested - known)
            raise ValueError(f"unknown ETL systems: {', '.join(unknown)}")
        return selected


def build_etl_pipeline(settings: Settings) -> ETLPipeline:
    return ETLPipeline(settings=settings)
