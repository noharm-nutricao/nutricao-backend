import pytest

def test_get_nutritional_patients_unauthorized(client):
    """Cenário: Token ausente (401) - Não passamos nenhum header"""
    response = client.get("/nutritional/patients")
    assert response.status_code == 401

def test_get_nutritional_patients_forbidden(client):
    """Cenário: Token válido, mas sem permissão (403)"""
    response = client.get("/nutritional/patients", headers={"Authorization": "Bearer viewer_token"})
    assert response.status_code in [401, 403]

def test_get_nutritional_patients_success(client, analyst_headers):
    """Cenário: Token válido com permissão (200)"""
    response = client.get("/nutritional/patients", headers=analyst_headers)

    assert response.status_code == 200

