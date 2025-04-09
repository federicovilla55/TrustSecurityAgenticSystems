from autogen_core import SingleThreadedAgentRuntime, AgentId

from src import *

class Client:
    def __init__(self, username : str):
        self._username = username
        self._token = None

    async def setup_user(self, user_content: str) -> None:
        await Runtime.send_message(SetupMessage(content=user_content, user=self._username), "my_agent", self._username)

    async def pause_user(self) -> None:
        answer = await Runtime.send_message(
                message=GetRequest(request_type=RequestType.PAUSE_AGENT, user=self._username),
                agent_type="orchestrator_agent",
        )

    async def resume_user(self) -> None:
        answer = await Runtime.send_message(
                message=GetRequest(request_type=RequestType.PAUSE_AGENT, user=self._username),
                agent_type="orchestrator_agent",
        )

    async def delete_user(self) -> None:
        answer = await Runtime.send_message(
                message=GetRequest(request_type=RequestType.PAUSE_AGENT, user=self._username),
                agent_type="orchestrator_agent",
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
        # this should return
        ...

    async def get_public_information(self):
        # ask MyAgent for my public information
        print(f"{self._username} public information: ")

    async def get_private_information(self):
        # ask MyAgent for my private information
        print(f"{self._username} private information: ")

    async def policies(self):
        # ask MyAgent for my policies
        print(f"{self._username} policies: ")

    async def send_feedback(self, relation_id : str, feedback : bool):
        # give feedback in one of the multiple types of agent relation
        print()

    async def save_configuration(self):
        ...

    async def load_configuration(self):
        ...