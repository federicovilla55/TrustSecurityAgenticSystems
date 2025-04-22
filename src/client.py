from typing import Optional

from src.models.messages import InitMessage
from src.runtime import Runtime
from src.enums import Status, ActionType, AgentRelations, RequestType, Relation
from src.models import SetupMessage, ActionRequest, UserInformation, GetRequest, FeedbackMessage
import httpx


class Client:
    def __init__(self, username : str):
        self._username = username
        self._token : Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

        print(f"Client Initialized: {self._username}")

    async def __aenter__(self):
        self._client = httpx.AsyncClient()
        return self

    async def init_agent(self):
        print("INIT AGENT")
        await Runtime.send_message(InitMessage(), "my_agent", self._username)

    async def setup_user(self, user_content: str) -> Status:
        return await Runtime.send_message(SetupMessage(content=user_content, user=self._username), "my_agent", self._username)

    async def pause_user(self) -> Status:
        return await Runtime.send_message(
            message=ActionRequest(request_type=ActionType.PAUSE_AGENT.value, user=self._username),
            agent_type="my_agent", agent_key=self._username
        )


    async def resume_user(self) -> Status:
        return await Runtime.send_message(
            message=ActionRequest(request_type=ActionType.RESUME_AGENT.value, user=self._username),
            agent_type="my_agent",
            agent_key=self._username
        )

    async def delete_user(self) -> Status:
        return await Runtime.send_message(
            message=ActionRequest(request_type=ActionType.DELETE_AGENT.value, user=self._username),
            agent_type="my_agent",
            agent_key=self._username
        )

    async def get_agent_established_relations(self) -> AgentRelations:
        # this should return the relations the agents has made, so the agents that have been connected and confirmed by the agent only
        matches = (
            await Runtime.send_message(
                    message=GetRequest(request_type=RequestType.GET_PERSONAL_RELATIONS.value, user=self._username),
                    agent_type="orchestrator_agent",
            )
        )

        return matches

    async def get_pairing(self) -> AgentRelations:
        # this should return the relations the agents have made and that the humans have confirmed.
        pairings = (
            await Runtime.send_message(
                message=GetRequest(request_type=RequestType.GET_PERSONAL_RELATIONS.value, user=self._username),
                agent_type="orchestrator_agent",
            )
        )

        return pairings.agents_relation

    async def get_agent_failed_relations(self):
        # To Implement
        pass

    async def get_public_information(self) -> dict:
        # ask MyAgent for my public information
        get_response : UserInformation = (
            await Runtime.send_message(
                message=GetRequest(request_type=RequestType.GET_PUBLIC_INFORMATION.value, user=self._username),
                agent_type="my_agent",
                agent_key=self._username
            )
        )

        return get_response.public_information

    async def get_private_information(self) -> dict:
        # ask MyAgent for my private information
        get_response : UserInformation = (
            await Runtime.send_message(
                message=GetRequest(request_type=RequestType.GET_PRIVATE_INFORMATION.value, user=self._username),
                agent_type="my_agent",
                agent_key=self._username
            )
        )

        return get_response.private_information
    
    async def get_policies(self) -> dict:
        # ask MyAgent for my policies
        get_response : UserInformation = (
            await Runtime.send_message(
                message=GetRequest(request_type=RequestType.GET_POLICIES.value, user=self._username),
                agent_type="my_agent",
                agent_key=self._username
            )
        )

        return get_response.policies

    async def get_information(self) -> dict:
        get_response : UserInformation = (
            await Runtime.send_message(
                message=GetRequest(request_type=RequestType.GET_USER_INFORMATION.value, user=self._username),
                agent_type="my_agent",
                agent_key=self._username
            )
        )

        return {
            'policies' : get_response.policies,
            'public_information' : get_response.public_information,
            'private_information' : get_response.private_information,
            'isSetup' : get_response.is_setup
        }
    
    async def change_information(self, public_information : dict, private_information : dict, policies : dict) -> Status:
        return await Runtime.send_message(
            message=UserInformation(
                public_information=public_information,
                private_information=private_information,
                policies=policies,
                username=self._username
            ),
            agent_type="my_agent",
            agent_key=self._username
        )

    async def send_feedback(self, receiver : str, accepted : bool) -> Status:
        if accepted:
            feedback = Relation.USER_ACCEPTED
        else:
            feedback = Relation.USER_REFUSED

        sender = self._username

        return await Runtime.send_message(
            message=FeedbackMessage(
                sender=sender,
                receiver=receiver,
                feedback=feedback.value,
            ),
            agent_type="orchestrator_agent",
        )

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