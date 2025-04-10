import json
import time

import pytest
from fastapi.testclient import TestClient
from ..fast_api.sample_api import app, database, SECRET_KEY
from src import Runtime, get_model, ModelType, register_agents, SetupMessage, Client
from jose import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
import pytest_asyncio
from enum import Enum
from unittest.mock import MagicMock

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Enum):
            return o.value
        return super().default(o)

@pytest.fixture
def test_client():
    database.clear()
    database["testuser"] = {
        "username": "testuser",
        "hashed_password": pwd_context.hash("secret"),
        "disabled": False
    }
    yield TestClient(app)

@pytest_asyncio.fixture
async def register_runtime():
    Runtime.start_runtime()
    try:
        model_name = "meta-llama/Llama-3.3-70B-Instruct"
        model_client = get_model(model_type=ModelType.OLLAMA, model=model_name)
        await register_agents(model_client)
    except Exception as e:
        print(f"Error during runtime registration: {e}")
        pass
    yield

@pytest_asyncio.fixture
async def cleanup_runtime():
    yield
    print("CLEAN")
    await Runtime.stop_runtime_when_idle()
    await Runtime.close_runtime()


def test_authentication(test_client):
    response = test_client.post("/api/token",
        data={
            "username": "testuser",
            "password": "secret"
        }
    )
    assert response.status_code == 200
    assert "access_token" in response.json()

    response = test_client.post("/api/token", data={
        "username": "invalid_user",
        "password": "invalid_password"
    })

    assert response.status_code == 401

@pytest.mark.asyncio
async def test_protected_endpoints(test_client, register_runtime, cleanup_runtime):
    response = test_client.post("/api/token",
        data={
            "username": "testuser",
            "password": "secret"
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    response = test_client.post("/api/setup",
        json={
            "user": "testuser",
            "content": "content_test",
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    print("resp: ", response)
    assert response.status_code == 200

def test_agent_operations(test_client, register_runtime, cleanup_runtime):
    # Get valid token with correct credentials
    auth_response = test_client.post("/api/token", data={
        "username": "testuser",
        "password": "secret"
    })
    assert auth_response.status_code == 200
    token = auth_response.json()["access_token"]

    response = test_client.post("/api/setup",
        json={
            "user": "testuser",
            "content": "",
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200

    # Test operations
    for endpoint in ["/api/pause", "/api/resume", "/api/delete"]:
        response = test_client.post(
            endpoint,
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200