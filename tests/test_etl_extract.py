import os

import pytest

from app.etl.extract import ExtractError, SecretStore


class _Payload:
    def __init__(self, data: bytes) -> None:
        self.data = data


class _AccessResponse:
    def __init__(self, value: str) -> None:
        self.payload = _Payload(value.encode("utf-8"))


class StubSecretManagerClient:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.requested_names: list[str] = []

    def access_secret_version(self, name: str):
        self.requested_names.append(name)
        if name not in self.values:
            raise RuntimeError(f"secret not found: {name}")
        return _AccessResponse(self.values[name])


def test_secret_store_reads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCH_APP_ETL_SECRET_SAMPLE", "secret-value")

    store = SecretStore(use_secret_manager=False)

    assert store.get("SEARCH_APP_ETL_SECRET_SAMPLE") == "secret-value"


def test_secret_store_reads_from_secret_manager_by_secret_id() -> None:
    client = StubSecretManagerClient(
        {
            "projects/demo-project/secrets/my-secret/versions/latest": "secret-from-sm",
        }
    )
    store = SecretStore(
        use_secret_manager=True,
        project_id="demo-project",
        client=client,
    )

    value = store.get("my-secret")

    assert value == "secret-from-sm"
    assert client.requested_names == ["projects/demo-project/secrets/my-secret/versions/latest"]


def test_secret_store_reads_from_full_resource_name() -> None:
    resource_name = "projects/demo-project/secrets/my-secret/versions/3"
    client = StubSecretManagerClient({resource_name: "secret-v3"})
    store = SecretStore(use_secret_manager=True, project_id="demo-project", client=client)

    value = store.get(resource_name)

    assert value == "secret-v3"
    assert client.requested_names == [resource_name]


def test_secret_store_requires_project_id_in_secret_manager_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    store = SecretStore(use_secret_manager=True, project_id=None, client=StubSecretManagerClient({}))

    with pytest.raises(ExtractError):
        store.get("my-secret")
