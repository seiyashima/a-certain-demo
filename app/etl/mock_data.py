from __future__ import annotations

from typing import Any


MOCK_SECRET_VALUES: dict[str, str] = {
    "SEARCH_APP_ETL_SECRET_SERVICENOW_OKTA_CLIENT_ID": "mock-servicenow-client-id",
    "SEARCH_APP_ETL_SECRET_SERVICENOW_OKTA_CLIENT_SECRET": "mock-servicenow-client-secret",
    "SEARCH_APP_ETL_SECRET_WORKDAY_ENTRA_CLIENT_ID": "mock-workday-client-id",
    "SEARCH_APP_ETL_SECRET_WORKDAY_ENTRA_CLIENT_SECRET": "mock-workday-client-secret",
    "SEARCH_APP_ETL_SECRET_COMPLIANCE_LDAP_USERNAME": "cn=readonly,ou=svc,dc=demo,dc=local",
    "SEARCH_APP_ETL_SECRET_COMPLIANCE_LDAP_PASSWORD": "mock-ldap-password",
    "SEARCH_APP_ETL_SECRET_SHAREPOINT_ENTRA_CLIENT_ID": "mock-sharepoint-client-id",
    "SEARCH_APP_ETL_SECRET_SHAREPOINT_ENTRA_CLIENT_SECRET": "mock-sharepoint-client-secret",
    "SEARCH_APP_ETL_SECRET_CONFLUENCE_OKTA_CLIENT_ID": "mock-confluence-client-id",
    "SEARCH_APP_ETL_SECRET_CONFLUENCE_OKTA_CLIENT_SECRET": "mock-confluence-client-secret",
}


MOCK_ETL_RECORDS: dict[str, list[dict[str, Any]]] = {
    "servicenow": [
        {
            "id": "sn-1001",
            "title": "VPN incident runbook",
            "content": "ServiceNow incident response for VPN outage.",
            "allowed_groups": ["ops", "it-support"],
            "allowed_regions": ["apac"],
        }
    ],
    "workday": [
        {
            "id": "wd-2001",
            "title": "Payroll adjustment process",
            "content": "Workday payroll correction flow.",
            "allowed_departments": ["hr"],
            "allowed_positions": ["manager"],
        }
    ],
    "compliance-system": [
        {
            "id": "cp-3001",
            "title": "Trading violation checklist",
            "content": "Compliance checklist for market conduct investigations.",
            "allowed_groups": ["compliance-officer"],
            "allowed_departments": ["compliance"],
        }
    ],
    "sharepoint": [
        {
            "id": "sp-4001",
            "title": "Policy template library",
            "content": "SharePoint policy template and governance notes.",
            "allowed_regions": ["emea", "apac"],
        }
    ],
    "confluence": [
        {
            "id": "cf-5001",
            "title": "Connector architecture decision",
            "content": "Confluence page with connector ETL and ACL notes.",
            "allowed_user_subs": ["user-demo-001", "user-demo-ops"],
        }
    ],
}


def get_mock_secret(secret_name: str) -> str:
    if secret_name in MOCK_SECRET_VALUES:
        return MOCK_SECRET_VALUES[secret_name]
    raise KeyError(secret_name)


def get_mock_records(system_name: str) -> list[dict[str, Any]]:
    return [dict(item) for item in MOCK_ETL_RECORDS.get(system_name.strip().lower(), [])]


def build_mock_access_token(system_name: str, identity_provider: str) -> str:
    return f"mock-{identity_provider}-{system_name}-token"
