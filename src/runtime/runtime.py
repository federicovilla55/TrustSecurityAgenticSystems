import os
from typing import Optional
from autogen_core import SingleThreadedAgentRuntime, AgentId, RoutedAgent
from autogen_core.models import ChatCompletionClient
import asyncio

from autogen_ext.models.openai import OpenAIChatCompletionClient

from src.agents import OrchestratorAgent, MyAgent
from src.enums import ModelType

"""
Singleton class for the SingleThreadedAgentRuntime.
"""


class Runtime:
    _instance: Optional[SingleThreadedAgentRuntime] = None

    @classmethod
    def _get_instance(cls) -> SingleThreadedAgentRuntime:
        if cls._instance is None:
            print("NEW RUNTIME")
            cls._instance = SingleThreadedAgentRuntime()

        return cls._instance

    @classmethod
    def start_runtime(cls, model_type : Optional[ModelType] = None, model : Optional[str] = None,
                      temperature_my_agent : Optional[float] = None, temperature_orchestrator : Optional[float] = None) -> None:
        instance = cls._get_instance()

        print("START.")
        instance.start()

    @classmethod
    async def stop_runtime(cls) -> None:
        print("Starting Closure...")

        instance = cls._get_instance()
        await instance.stop_when_idle()

        await cls.close_runtime()

    @classmethod
    async def close_runtime(cls) -> None:
        instance = cls._get_instance()
        await instance.close()
        print("Runtime Closed")

    @classmethod
    async def register_orchestrator(cls, model_client: ChatCompletionClient):
        await OrchestratorAgent.register(
            cls._get_instance(),
            "orchestrator_agent",
            lambda: OrchestratorAgent(
                model_client=model_client,
            )
        )

        print("Orchestrator Registered")

    @classmethod
    async def register_my_agent(cls, model_client: ChatCompletionClient):
        await MyAgent.register(
            cls._get_instance(),
            "my_agent",
            lambda: MyAgent(
                model_client=model_client,
            )
        )

        print("My Agent Registered")

    @classmethod
    async def send_message(cls, message, agent_type, agent_key="default"):
        instance = cls._get_instance()
        agent_id = AgentId(agent_type, agent_key)

        print(f"SENDING TO: {agent_id} the {message}")
        return await instance.send_message(message, agent_id)

    @classmethod
    async def get_agent_relations(cls, message) -> dict:
        instance = cls._get_instance()
        answer = await instance.send_message(message, AgentId("orchestrator_agent", "default"))
        return answer.agents_relation

    @classmethod
    async def get_registered_agents(cls, message) -> set[str]:
        instance = cls._get_instance()
        answer = await instance.send_message(message, AgentId("orchestrator_agent", "default"))
        return answer.registered_agents

    @classmethod
    def configure_runtime(cls, model_type : ModelType, model : str = None, temperature_my_agent : float = 0.5,
                          temperature_orchestrator : float = 0.5) -> None:
        model_my_agent = get_model(model_type, model, temperature_my_agent)
        model_orchestrator = get_model(model_type, model, temperature_orchestrator)

        asyncio.run(Runtime.register_my_agent(model_client=model_my_agent))
        asyncio.run(Runtime.register_orchestrator(model_client=model_orchestrator))


def get_model(model_type : ModelType, model : Optional[str] = None, temperature : float = 0.5) -> ChatCompletionClient:
    if model_type == ModelType.OLLAMA:
        # Specify if there is a special url that, otherwise use the standard one.
        if os.getenv('API_KEY'):
            api_key = os.getenv('API_KEY')
        else:
            api_key = ""
        if os.getenv('BASE_URL'):
            base_url = os.getenv('BASE_URL')
        else:
            print("No BASE_URL environment variable found. Using default.")
            # Ollama base url
            base_url = "http://localhost:11434/v1"

        model_client = OpenAIChatCompletionClient(
            model= model if model else "llama3.2:3b",
            base_url=base_url,
            api_key=api_key,
            temperature=temperature,
            model_info={
                "vision": False,
                "function_calling": True,
                "json_output": False,
                "family": "unknown",
                "structured_output" : False,
            },
        )
    elif model_type == ModelType.OPENAI:
        if not os.getenv("OPENAI_API_KEY"):
            print("Please set OPENAI_API_KEY environment variable.")
            exit()
        model_client = OpenAIChatCompletionClient(model=(model if model else "gpt-4o"), api_key=os.getenv("OPENAI_API_KEY"))
    elif model_type == ModelType.GEMINI:
        if not os.getenv("GEMINI_API_KEY"):
            print("Please set GEMINI_API_KEY environment variable.")
            exit()
        model_client = OpenAIChatCompletionClient(
            model=model if model else "gemini-1.5-flash",
            api_key=os.getenv("GEMINI_API_KEY"),
        )
    else:
        model_client = None
        print("No model selected.")
        exit()

    return model_client

async def register_agents(model_client : ChatCompletionClient):
    await Runtime.register_my_agent(model_client=model_client)
    await Runtime.register_orchestrator(model_client=model_client)

async def register_orchestrator(model_client : ChatCompletionClient):
    await Runtime.register_orchestrator(model_client=model_client)

async def register_my_agent(model_client : ChatCompletionClient):
    await Runtime.register_my_agent(model_client=model_client)

