from typing import Optional
from autogen_core import SingleThreadedAgentRuntime, AgentId, RoutedAgent
from autogen_core.models import ChatCompletionClient
import asyncio

from src import OrchestratorAgent, MyAgent

"""
Singleton class for the SingleThreadedAgentRuntime.
"""


class Runtime:
    _instance: Optional[SingleThreadedAgentRuntime] = None
    _shutdown_flag = False

    @classmethod
    def _get_instance(cls) -> SingleThreadedAgentRuntime:
        if cls._instance is None:
            cls._instance = SingleThreadedAgentRuntime()
        return cls._instance

    @classmethod
    def start_runtime(cls) -> None:
        instance = cls._get_instance()
        cls._shutdown_flag = False
        instance.start()

    @classmethod
    async def stop_runtime(cls) -> None:
        cls._shutdown_flag = True

        instance = cls._get_instance()
        await instance.stop_when_idle()

    @classmethod
    async def close_runtime(cls) -> None:
        instance = cls._get_instance()
        await instance.close()

    @classmethod
    async def register_orchestrator(cls, model_client: ChatCompletionClient):
        await OrchestratorAgent.register(
            cls._get_instance(),
            "orchestrator_agent",
            lambda: OrchestratorAgent(
                model_client=model_client,
                description="A helpful orchestrator agent."
            )
        )

    @classmethod
    async def register_my_agent(cls, model_client: ChatCompletionClient):
        await MyAgent.register(
            cls._get_instance(),
            "my_agent",
            lambda: MyAgent(
                model_client=model_client,
                description="A helpful personal agent."
            )
        )

    @classmethod
    async def send_message(cls, message, agent_type, agent_key="default"):
        if cls._shutdown_flag:
            raise RuntimeError("Runtime is shutting down")
        
        instance = cls._get_instance()
        #print(f"SENDING {message} TO: {AgentId(agent_type, agent_key)}")
        return await instance.send_message(message, AgentId(agent_type, agent_key))

    @classmethod
    async def get_agent_relations(cls, message) -> dict:
        answer = await cls.send_message(message, "orchestrator_agent")
        return answer.agents_relation

    @classmethod
    async def get_registered_agents(cls, message) -> set[str]:
        answer = await cls.send_message(message, "orchestrator_agent")
        return answer.registered_agents
