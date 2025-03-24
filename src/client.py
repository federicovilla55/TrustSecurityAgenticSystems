from autogen_core import SingleThreadedAgentRuntime, AgentId

from src import *

class Client:
    def __init__(self, username : str):
        self._username = username

    async def setup_user(self, user_content: str) -> None:
        await Runtime.send_message(SetupMessage(content=user_content, user=self._username), "my_agent", self._username)

    async def get_agent_established_relations(self):
        # this should return the relations the agents has made, so the agents that have been connected and confirmed by the agent only
        print()

    async def get_pairing(self):
        # this should return the relations the agents have made and that the humans have confirmed.
        print()

    async def get_agent_failed_relations(self):
        # this should return
        print()

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