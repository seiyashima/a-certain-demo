from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app, get_etl_pipeline


class StubPipeline:
    async def run(self, systems=None, dry_run=False):
        if systems and "unknown" in systems:
            raise ValueError("unknown ETL systems: unknown")
        return [
            type(
                "Result",
                (),
                {
                    "system": "servicenow",
                    "extracted_records": 3,
                    "transformed_documents": 3,
                    "loaded_documents": 3 if not dry_run else 0,
                },
            )()
        ]


def teardown_module() -> None:
    app.dependency_overrides.clear()


def test_etl_run_rejects_when_disabled() -> None:
    settings = Settings(api_key="1234567890abcdef")
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_etl_pipeline] = lambda: StubPipeline()
    client = TestClient(app)

    response = client.post(
        "/etl/run",
        headers={"x-api-key": "1234567890abcdef"},
        json={"dry_run": True},
    )

    assert response.status_code == 503


def test_etl_run_returns_summary() -> None:
    settings = Settings(
        api_key="1234567890abcdef",
        etl_enabled=True,
        etl_systems=[
            {
                "name": "servicenow",
                "identity_provider": "okta",
                "extract_url": "https://api.servicenow.example.com/v1/documents",
                "token_url": "https://example.okta.com/oauth2/default/v1/token",
                "client_id_secret": "SEARCH_APP_ETL_SECRET_SERVICENOW_OKTA_CLIENT_ID",
                "client_secret_secret": "SEARCH_APP_ETL_SECRET_SERVICENOW_OKTA_CLIENT_SECRET",
            }
        ],
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_etl_pipeline] = lambda: StubPipeline()
    client = TestClient(app)

    response = client.post(
        "/etl/run",
        headers={"x-api-key": "1234567890abcdef"},
        json={"dry_run": False, "systems": ["servicenow"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "dry_run": False,
        "systems": [
            {
                "system": "servicenow",
                "extracted_records": 3,
                "transformed_documents": 3,
                "loaded_documents": 3,
            }
        ],
    }


def test_etl_run_returns_400_for_unknown_systems() -> None:
    settings = Settings(
        api_key="1234567890abcdef",
        etl_enabled=True,
        etl_systems=[
            {
                "name": "servicenow",
                "identity_provider": "okta",
                "extract_url": "https://api.servicenow.example.com/v1/documents",
                "token_url": "https://example.okta.com/oauth2/default/v1/token",
                "client_id_secret": "SEARCH_APP_ETL_SECRET_SERVICENOW_OKTA_CLIENT_ID",
                "client_secret_secret": "SEARCH_APP_ETL_SECRET_SERVICENOW_OKTA_CLIENT_SECRET",
            }
        ],
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_etl_pipeline] = lambda: StubPipeline()
    client = TestClient(app)

    response = client.post(
        "/etl/run",
        headers={"x-api-key": "1234567890abcdef"},
        json={"systems": ["unknown"]},
    )

    assert response.status_code == 400
