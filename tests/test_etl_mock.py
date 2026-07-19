from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


def teardown_module() -> None:
    app.dependency_overrides.clear()


def _mock_mode_settings() -> Settings:
    return Settings(
        api_key="1234567890abcdef",
        etl_enabled=True,
        etl_mock_mode=True,
        etl_systems=[
            {
                "name": "servicenow",
                "identity_provider": "okta",
                "extract_url": "https://api.servicenow.example.com/v1/documents",
                "token_url": "https://example.okta.com/oauth2/default/v1/token",
                "client_id_secret": "SEARCH_APP_ETL_SECRET_SERVICENOW_OKTA_CLIENT_ID",
                "client_secret_secret": "SEARCH_APP_ETL_SECRET_SERVICENOW_OKTA_CLIENT_SECRET",
            },
            {
                "name": "workday",
                "identity_provider": "entra_id",
                "extract_url": "https://api.workday.example.com/v1/workers",
                "token_url": "https://login.microsoftonline.com/demo/oauth2/v2.0/token",
                "client_id_secret": "SEARCH_APP_ETL_SECRET_WORKDAY_ENTRA_CLIENT_ID",
                "client_secret_secret": "SEARCH_APP_ETL_SECRET_WORKDAY_ENTRA_CLIENT_SECRET",
            },
            {
                "name": "compliance-system",
                "identity_provider": "okta_ldap_agent",
                "extract_url": "https://compliance.example.com/api/v1/records",
                "username_secret": "SEARCH_APP_ETL_SECRET_COMPLIANCE_LDAP_USERNAME",
                "password_secret": "SEARCH_APP_ETL_SECRET_COMPLIANCE_LDAP_PASSWORD",
            },
            {
                "name": "sharepoint",
                "identity_provider": "entra_id",
                "extract_url": "https://graph.microsoft.com/v1.0/sites/demo/lists/demo/items",
                "token_url": "https://login.microsoftonline.com/demo/oauth2/v2.0/token",
                "client_id_secret": "SEARCH_APP_ETL_SECRET_SHAREPOINT_ENTRA_CLIENT_ID",
                "client_secret_secret": "SEARCH_APP_ETL_SECRET_SHAREPOINT_ENTRA_CLIENT_SECRET",
                "records_field": "value",
            },
            {
                "name": "confluence",
                "identity_provider": "okta",
                "extract_url": "https://confluence.example.com/wiki/rest/api/content",
                "token_url": "https://example.okta.com/oauth2/default/v1/token",
                "client_id_secret": "SEARCH_APP_ETL_SECRET_CONFLUENCE_OKTA_CLIENT_ID",
                "client_secret_secret": "SEARCH_APP_ETL_SECRET_CONFLUENCE_OKTA_CLIENT_SECRET",
                "records_field": "results",
            },
        ],
    )


def test_mock_endpoints_return_fixed_data() -> None:
    client = TestClient(app)

    records = client.get("/mock/systems/servicenow/records")
    assert records.status_code == 200
    assert records.json()["system"] == "servicenow"
    assert records.json()["items"][0]["id"] == "sn-1001"

    token = client.post("/mock/idp/okta/token", params={"system": "servicenow"})
    assert token.status_code == 200
    assert token.json()["access_token"].startswith("mock-okta-servicenow")

    bind = client.get("/mock/ldap/bind/compliance-system")
    assert bind.status_code == 200
    assert "username" in bind.json()


def test_etl_run_uses_mock_mode_for_all_five_systems() -> None:
    app.dependency_overrides[get_settings] = _mock_mode_settings
    client = TestClient(app)

    response = client.post(
        "/etl/run",
        headers={"x-api-key": "1234567890abcdef"},
        json={"dry_run": False},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert len(payload["systems"]) == 5
    assert all(item["loaded_documents"] >= 0 for item in payload["systems"])
