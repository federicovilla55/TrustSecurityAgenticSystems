import httpx
from autogen_core import SingleThreadedAgentRuntime, AgentId
import os

from src import *

class Client:
    def __init__(self, username : str):
        self._username = username
        self._token : Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient()
        return self

    async def setup_user(self, user_content: str) -> None:
        await Runtime.send_message(SetupMessage(content=user_content, user=self._username), "my_agent", self._username)

    async def pause_user(self) -> None:
        await Runtime.send_message(
            message=GetRequest(request_type=RequestType.PAUSE_AGENT.value, user=self._username),
            agent_type="my_agent", agent_key=self._username
        )

    async def resume_user(self) -> None:
        await Runtime.send_message(
            message=GetRequest(request_type=RequestType.RESUME_AGENT.value, user=self._username),
            agent_type="my_agent",
            agent_key=self._username
        )

    async def delete_user(self) -> None:
        await Runtime.send_message(
            message=GetRequest(request_type=RequestType.DELETE_AGENT.value, user=self._username),
            agent_type="my_agent",
            agent_key=self._username
        )

    async def get_agent_established_relations(self) -> None:
        # this should return the relations the agents has made, so the agents that have been connected and confirmed by the agent only
        matches = (
            await Runtime.send_message(
                    message=GetRequest(request_type=RequestType.GET_PERSONAL_RELATIONS, user=self._username),
                    agent_type="orchestrator_agent",
            )
        )

    async def get_pairing(self) -> AgentRelations:
        # this should return the relations the agents have made and that the humans have confirmed.
        pairings = (
            await Runtime.send_message(
                message=GetRequest(request_type=RequestType.GET_PERSONAL_RELATIONS, user=self._username),
                agent_type="orchestrator_agent",
            )
        )

        return pairings.agents_relation

    async def get_agent_failed_relations(self):
        # To Implement
        pass

    async def get_public_information(self) -> str:
        # ask MyAgent for my public information
        print(f"{self._username} public information: ")
        return ""

    async def get_private_information(self) -> str:
        # ask MyAgent for my private information
        print(f"{self._username} private information: ")
        return ""

    async def policies(self) -> str:
        # ask MyAgent for my policies
        print(f"{self._username} policies: ")
        return ""

    async def send_feedback(self, relation_id : str, feedback : bool):
        # give feedback in one of the multiple types of agent relation
        print()

    async def save_configuration(self):
        pass

    async def load_configuration(self):
        pass

    async def user_authentication(self, password: str):
        # Call /token endpoint to get JWT
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "/api/token",
                data={"username": self._username, "password": password}
            )
            response.raise_for_status()
            self._token = response.json()["access_token"]

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self._token}"}