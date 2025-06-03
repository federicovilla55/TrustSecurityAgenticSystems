import pytest
from fastapi.testclient import TestClient
from ..fast_api.python_api import app, SECRET_KEY
from src import Runtime, get_model, ModelType, register_agents, SetupMessage, Client, RequestType
from src.database import clear_database, close_database
from src.database import init_database
from passlib.context import CryptContext
import pytest_asyncio
import httpx

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@pytest.fixture
def test_client():
    """
    The fixture for the FastAPI test client.
    It clears the database before each test and closes the database connection after each test.

    :return: None
    """
    clear_database()
    close_database()
    yield TestClient(app)

@pytest_asyncio.fixture(scope="function")
async def register_runtime():
    """
    The fixture for registering the runtime.
    The runtime is started and stopped before and after each test.

    :return: None
    """
    init_database()
    Runtime.start_runtime()
    try:
        model_name = "meta-llama/Llama-3.3-70B-Instruct"
        model_client = get_model(model_type=ModelType.SWISSAI, model=model_name)
        await register_agents(model_client, model_name, {model_name : model_client})
    except Exception as e:
        print(f"Error during registration: {e}")
    yield

@pytest_asyncio.fixture(scope="function")
async def cleanup_runtime():
    """
    A fixture to clean up the runtime after each test.

    :return: None
    """
    yield
    print("Cleaning up runtime")
    await Runtime.stop_runtime()
    await Runtime.close_runtime()



def test_authentication(test_client, register_runtime, cleanup_runtime):
    """
    A synchronous test for authentication. The test checks if the correct credentials are accepted and invalid credentials are rejected.

    :param test_client: A FastAPI test client.
    :param register_runtime: A fixture to register the runtime.
    :param cleanup_runtime: A fixture to clean up the runtime after each test.
    :return: None
    """
    response = test_client.post("/api/register",
        json={
            "username": "testuser",
            "password": "secret"
    })
    assert response.status_code == 200
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


@pytest.mark.asyncio
async def test_protected_endpoints(test_client, register_runtime, cleanup_runtime):
    """
    Tests that endpoints requiring authentication work correctly using a valid JWT token.

    :param test_client: FastAPI TestClient used to make HTTP requests.
    :param register_runtime: Fixture to initialize model runtime.
    :param cleanup_runtime: Fixture to teardown model runtime.
    :return: None
    """
    # Use ASGITransport with the actual app instance
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Get token
        response = await client.post("/api/register",
            json={
                "username": "testuser",
                "password": "secret"
        })
        assert response.status_code == 200

        response = await client.post("/api/token", data={
            "username": "testuser",
            "password": "secret"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]

        # Access protected endpoint
        response = await client.post(
            "/api/setup",
            json={"user": "testuser", "content": "test", "default_value" : 1},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

        response = await client.post(
            "/api/delete",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200



@pytest.mark.asyncio
async def test_agent_operations(test_client, register_runtime, cleanup_runtime):
    """
    Tests `ActionType` operations: `pause`, `resume`, and `delete`.

    :param test_client: FastAPI TestClient used to make HTTP requests.
    :param register_runtime: Fixture to initialize model runtime.
    :param cleanup_runtime: Fixture to teardown model runtime.
    :return: None
    """
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Authenticate
        response = await client.post("/api/register",
            json={
                "username": "testuser",
                "password": "secret"
        })
        assert response.status_code == 200
        response = await client.post("/api/token", data={
            "username": "testuser",
            "password": "secret"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]

        response = await client.post(
            "/api/setup",
            json={"user": "testuser", "content": "test", "default_value" : 1},
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
    """
    Tests retrieval of user information from the FastAPI GET endpoints.

    :param test_client: FastAPI TestClient used to make HTTP requests.
    :param register_runtime: Fixture to initialize model runtime.
    :param cleanup_runtime: Fixture to teardown model runtime.
    :return: None
    """
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/register",
             json={
                 "username": "testuser",
                 "password": "secret"
         })
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
                "default_value": 1,
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

        response = await client.get(
            "/api/relations",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert 'relations' in response.json().keys()

        response = await client.post(
            "/api/delete",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_agent_change_information(test_client, register_runtime, cleanup_runtime):
    """
    Tests updating public information, private information and policies, and verifies the updates.

    :param test_client: FastAPI TestClient used to make HTTP requests.
    :param register_runtime: Fixture to initialize model runtime.
    :param cleanup_runtime: Fixture to teardown model runtime.
    :return: None
    """
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/register",
             json={
                 "username": "testuser",
                 "password": "secret"
         })
        assert response.status_code == 200

        auth_response = await client.post("/api/token", data={
            "username": "testuser",
            "password": "secret"
        })
        assert auth_response.status_code == 200
        token = auth_response.json()["access_token"]

        setup_response = await client.post("/api/setup",
            json={
                "user": "testuser",
                "content": "I am Alice, an ETH student. I study computer science and I want to connect to other students from ETH or workers from Big tech companies.",
                "default_value" : 1
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert setup_response.status_code == 200

        new_public_information = {"public_info_1" : "test"}
        new_private_information = {"private_info_1" : "test"}
        new_policies = {"policy1" : "test"}

        change_response = await client.post(
            "api/change_information",
            json={
                "user": "testuser",
                "public_information" : new_public_information,
                "private_information" : new_private_information,
                "policies" : new_policies,
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert change_response.status_code == 200

        get_endpoint = "/api/get_information"
        public_info_response = await client.post(get_endpoint,
             json={
                 "type": RequestType.GET_PUBLIC_INFORMATION.value,
             },
             headers={"Authorization": f"Bearer {token}"}
         )

        assert public_info_response.status_code == 200
        assert 'public_information' in public_info_response.json().keys()
        assert public_info_response.json()['public_information'] == new_public_information

        policies_response = await client.post(get_endpoint,
             json={
                 "type": RequestType.GET_POLICIES.value,
             },
             headers={"Authorization": f"Bearer {token}"}
         )

        assert policies_response.status_code == 200
        assert 'policies' in policies_response.json().keys()
        assert policies_response.json()['policies'] == new_policies

        private_info_response = await client.post(get_endpoint,
             json={
                 "type": RequestType.GET_PRIVATE_INFORMATION.value,
             },
             headers={"Authorization": f"Bearer {token}"}
         )

        assert private_info_response.status_code == 200
        assert 'private_information' in private_info_response.json().keys()
        assert private_info_response.json()['private_information'] == new_private_information

        response = await client.post(
            "/api/delete",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200



@pytest.mark.asyncio
async def test_unchanged_setup_repeated(test_client, register_runtime, cleanup_runtime):
    """
    Tests that re-setting the same agent by invoking again the setup is correctly rejected and verifies that no information is lost or overwritten.

    :param test_client: FastAPI TestClient used to make HTTP requests.
    :param register_runtime: Fixture to initialize model runtime.
    :param cleanup_runtime: Fixture to teardown model runtime.
    :return: None
    """
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/register",
             json={
                 "username": "testuser",
                 "password": "secret"
         })
        assert response.status_code == 200
        auth_response = await client.post("/api/token", data={
            "username": "testuser",
            "password": "secret"
        })
        assert auth_response.status_code == 200
        token = auth_response.json()["access_token"]

        setup_response = await client.post("/api/setup",
            json={
                "user": "testuser",
                "content": "I am Alice, an ETH student. I study computer science and I want to connect to other students from ETH or workers from Big tech companies.",
                "default_value" : 1
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert setup_response.status_code == 200

        new_public_information = {"public_info_1" : "test"}
        new_private_information = {"private_info_1" : "test"}
        new_policies = {"policy1" : "test"}

        change_response = await client.post(
            "api/change_information",
            json={
                "user": "testuser",
                "public_information" : new_public_information,
                "private_information" : new_private_information,
                "policies" : new_policies,
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert change_response.status_code == 200

        new_setup_response = await client.post("/api/setup",
            json={
                "user": "testuser",
                "content": "I am Alice, an ETH student. I study computer science and I want to connect to other students from ETH or workers from Big tech companies.",
                "default_value": 1
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert new_setup_response.status_code == 400

        get_endpoint = "/api/get_information"
        public_info_response = await client.post(get_endpoint,
             json={
                 "type": RequestType.GET_PUBLIC_INFORMATION.value,
             },
             headers={"Authorization": f"Bearer {token}"}
         )

        assert public_info_response.status_code == 200
        assert 'public_information' in public_info_response.json().keys()
        assert public_info_response.json()['public_information'] == new_public_information

        policies_response = await client.post(get_endpoint,
             json={
                 "type": RequestType.GET_POLICIES.value,
             },
             headers={"Authorization": f"Bearer {token}"}
         )

        assert policies_response.status_code == 200
        assert 'policies' in policies_response.json().keys()
        assert policies_response.json()['policies'] == new_policies

        private_info_response = await client.post(get_endpoint,
             json={
                 "type": RequestType.GET_PRIVATE_INFORMATION.value,
             },
             headers={"Authorization": f"Bearer {token}"}
         )

        assert private_info_response.status_code == 200
        assert 'private_information' in private_info_response.json().keys()
        assert private_info_response.json()['private_information'] == new_private_information

        response = await client.post(
            "/api/delete",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_relations_human_feedback(test_client, register_runtime, cleanup_runtime):
    """
    Tests the complete agent flow so registration, setup, updating information, retrieving relations, and submitting human feedback to a received pairing request.

    :param test_client: FastAPI TestClient used to make HTTP requests.
    :param register_runtime: Fixture to initialize model runtime.
    :param cleanup_runtime: Fixture to teardown model runtime.
    :return: None
    """
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/register",
             json={
                 "username": "testuser",
                 "password": "secret"
         })
        assert response.status_code == 200
        auth_response = await client.post("/api/token", data={
            "username": "testuser",
            "password": "secret"
        })
        assert auth_response.status_code == 200
        token = auth_response.json()["access_token"]

        setup_response = await client.post("/api/setup",
            json={
                "user": "testuser",
                "content": "I am Alice, an ETH student. I study computer science and I want to connect to other students from ETH or workers from Big tech companies.",
                "default_value": 1
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert setup_response.status_code == 200

        new_public_information = {"public_info_1" : "test"}
        new_private_information = {"private_info_1" : "test"}
        new_policies = {"policy1" : "test"}

        change_response = await client.post(
            "api/change_information",
            json={
                "user": "testuser",
                "public_information" : new_public_information,
                "private_information" : new_private_information,
                "policies" : new_policies,
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert change_response.status_code == 200

        get_endpoint = "/api/get_information"
        response = await client.post(get_endpoint,
             json={
                 "type": RequestType.GET_USER_INFORMATION.value,
             },
             headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert 'public_information' in response.json().keys()
        assert response.json()['public_information'] == new_public_information
        assert 'policies' in response.json().keys()
        assert response.json()['policies'] == new_policies
        assert 'private_information' in response.json().keys()
        assert response.json()['private_information'] == new_private_information

        response = await client.get(
            "/api/relations",
             headers={"Authorization": f"Bearer {token}"}
         )

        assert response.status_code == 200
        assert 'relations' in response.json().keys()

        response = await client.post("/api/feedback",
             json={
                 "receiver": 'Bob',
                 'feedback': True,
             },
             headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

        response = await client.post(
            "/api/delete",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
