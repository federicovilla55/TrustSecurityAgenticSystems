from typing import Optional
from autogen_core import SingleThreadedAgentRuntime, AgentId, RoutedAgent
from autogen_core.models import ChatCompletionClient

from src import OrchestratorAgent, MyAgent

"""
Singleton class for the SingleThreadedAgentRuntime.
"""
class Runtime:
    _instance : Optional[SingleThreadedAgentRuntime] = None

    @classmethod
    def _get_instance(cls) -> SingleThreadedAgentRuntime:
        if cls._instance is None:
            cls._instance = SingleThreadedAgentRuntime()
        return cls._instance

    @classmethod
    async def start_runtime(cls) -> None:
        instance = cls._get_instance()
        instance.start()

    @classmethod
    async def stop_runtime(cls) -> None:
        instance = cls._get_instance()
        await instance.stop_when_idle()

    @classmethod
    async def close_runtime(cls) -> None:
        instance = cls._get_instance()
        await instance.close()

    @classmethod
    async def register_orchestrator(cls, model_client : ChatCompletionClient):
        await OrchestratorAgent.register(cls._get_instance(), "orchestrator_agent",
                                         lambda: OrchestratorAgent(model_client=model_client, description="An helpful orchestrator agent."))
    @classmethod
    async def register_my_agent(cls, model_client : ChatCompletionClient):
        await MyAgent.register(cls._get_instance(), "my_agent",
                               lambda: MyAgent(model_client=model_client, description="An helpful personal agent."))
    @classmethod
    async def send_message(cls, message, agent_type: str, agent_key: Optional[str] = None):
        instance = cls._get_instance()
        return await instance.send_message(message, AgentId(agent_type, agent_key if agent_key else "default"))

    @classmethod
    async def get_agent_relations(cls, message) -> dict:
        answer = await cls.send_message(message, "orchestrator_agent", )
        return answer.agents_relation

    @classmethod
    async def get_registered_agents(cls, message) -> set[str]:
        answer = await cls.send_message(message, "orchestrator_agent", )
        return answer.registered_agents