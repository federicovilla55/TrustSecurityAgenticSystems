import json
import time

import pytest
from fastapi.testclient import TestClient
from ..fast_api.sample_api import app, database, SECRET_KEY
from src import Runtime, get_model, ModelType, register_agents, SetupMessage, Client, RequestType
from jose import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
import pytest_asyncio
from enum import Enum
import httpx
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
    yield TestClient(app)  # Ensure this yields the actual FastAPI app instance

@pytest_asyncio.fixture(scope="function")  # Add function scope
async def register_runtime():
    Runtime.start_runtime()
    try:
        model_name = "meta-llama/Llama-3.3-70B-Instruct"
        model_client = get_model(model_type=ModelType.OLLAMA, model=model_name)
        await register_agents(model_client)
    except Exception as e:
        print(f"Error during registration: {e}")
    yield

@pytest_asyncio.fixture(scope="function")  # Add function scope
async def cleanup_runtime():
    yield
    print("Cleaning up runtime")
    await Runtime.stop_runtime_when_idle()
    await Runtime.close_runtime()



# Synchronous test for authentication
def test_authentication(test_client):
    # Test valid credentials
    response = test_client.post("/api/token", data={
        "username": "testuser",
        "password": "secret"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

    # Test invalid credentials
    response = test_client.post("/api/token", data={
        "username": "invalid_user",
        "password": "invalid_password"
    })
    assert response.status_code == 401


# Update test_protected_endpoints and test_agent_operations tests

@pytest.mark.asyncio
async def test_protected_endpoints(test_client, register_runtime, cleanup_runtime):
    # Use ASGITransport with the actual app instance
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Get token
        response = await client.post("/api/token", data={
            "username": "testuser",
            "password": "secret"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]

        # Access protected endpoint
        response = await client.post(
            "/api/setup",
            json={"user": "testuser", "content": "test"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_agent_operations(test_client, register_runtime, cleanup_runtime):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Authenticate
        response = await client.post("/api/token", data={
            "username": "testuser",
            "password": "secret"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]

        response = await client.post(
            "/api/setup",
            json={"user": "testuser", "content": "test"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

        # Test agent operations
        for endpoint in ["/api/pause", "/api/resume", "/api/delete"]:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_agent_get_information(test_client, register_runtime, cleanup_runtime):
    # Get valid token with correct credentials
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        auth_response = await client.post("/api/token", data={
            "username": "testuser",
            "password": "secret"
        })
        assert auth_response.status_code == 200
        token = auth_response.json()["access_token"]

        response = await client.post("/api/setup",
            json={
                "user": "testuser",
                "content": "I am Alice, an ETH student. I study computer science and I want to connect to other students from ETH or workers from Big tech companies.",
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

        get_endpoint = "/api/get_information"
        response = await client.post(get_endpoint,
            json={
                "type" : RequestType.GET_PUBLIC_INFORMATION.value,
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        print(response.json())
        assert 'public_information' in response.json().keys()

        response = await client.post(get_endpoint,
            json={
                "type": RequestType.GET_POLICIES.value,
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert 'policies' in response.json().keys()

        response = await client.post(get_endpoint,
            json={
                "type": RequestType.GET_PRIVATE_INFORMATION.value,
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert 'private_information' in response.json().keys()