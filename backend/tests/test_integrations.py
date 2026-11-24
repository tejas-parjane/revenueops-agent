from uuid import UUID

from tests.conftest import register


def test_expired_credentials_are_reported_and_block_sync(client):
    from sqlalchemy import select

    from app.core.encryption import encrypt_credentials
    from app.db.session import SessionLocal
    from app.models.entities import Integration

    _, headers = register(client)
    integrations = client.get("/api/v1/integrations", headers=headers).json()
    hubspot = next(item for item in integrations if item["provider"] == "hubspot")

    db = SessionLocal()
    integration = db.scalar(select(Integration).where(Integration.id == UUID(hubspot["id"])))
    integration.encrypted_credentials = encrypt_credentials({"expired": True})
    db.commit()
    db.close()

    response = client.post(f"/api/v1/integrations/{hubspot['id']}/sync", headers=headers)
    assert response.status_code == 400
    after = client.get("/api/v1/integrations", headers=headers).json()
    updated = next(item for item in after if item["provider"] == "hubspot")
    assert updated["connection_status"] == "expired"
    assert updated["last_error"]
