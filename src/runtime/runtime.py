import os
from typing import Optional, Dict
from autogen_core import SingleThreadedAgentRuntime, AgentId, RoutedAgent
from autogen_core.models import ChatCompletionClient
import asyncio

from autogen_ext.models.openai import OpenAIChatCompletionClient

from src.agents import OrchestratorAgent, MyAgent
from src.enums import ModelType

class Runtime:
    """
    Singleton class for the SingleThreadedAgentRuntime.
    """
    _instance: Optional[SingleThreadedAgentRuntime] = None

    @classmethod
    def _get_instance(cls) -> SingleThreadedAgentRuntime:
        """
        Singleton method to get the AutoGen defined instance.
        :return: A runtime instance `SingleThreadedAgentRuntime`.
        """
        if cls._instance is None:
            cls._instance = SingleThreadedAgentRuntime()

        return cls._instance

    @classmethod
    def start_runtime(cls, model_type : Optional[ModelType] = None, model : Optional[str] = None,
                      temperature_my_agent : Optional[float] = None, temperature_orchestrator : Optional[float] = None) -> None:
        """
        A method to start the AutoGen defined runtime.
        :param model_type: The model type or the specified model: Ollama, OpenAI, GEMINI or MISTRAL.
        :param model: The name of the model to be used.
        :param temperature_my_agent: The temperature of the LLM model to be used by the personal agent..
        :param temperature_orchestrator: The temperature of the LLM model to be used by the orchestrator agent.
        :return: None
        """
        instance = cls._get_instance()

        instance.start()

    @classmethod
    async def stop_runtime(cls) -> None:
        """
        Stops the AutoGen defined runtime.
        :return:
        """
        print("Starting Closure...")

        instance = cls._get_instance()
        await instance.stop_when_idle()

        await cls.close_runtime()

    @classmethod
    async def close_runtime(cls) -> None:
        """
        Close the AutoGen defined runtime.
        :return:
        """
        instance = cls._get_instance()
        await instance.close()
        print("Runtime Closed")

    @classmethod
    async def register_orchestrator(cls, model_client: ChatCompletionClient, model_client_name : str):
        """
        Register the orchestrator agent.
        :param model_client: The ChatCompletionClient to be used by the orchestrator agent.
        :param model_client_name: The model name of the orchestrator agent.
        :return: None
        """
        await OrchestratorAgent.register(
            cls._get_instance(),
            "orchestrator_agent",
            lambda: OrchestratorAgent(
                model_client=model_client,
                model_client_name=model_client_name,
            )
        )

        print("Orchestrator Registered")

    @classmethod
    async def register_my_agent(cls, model_client: ChatCompletionClient, model_clients : Dict[str, ChatCompletionClient]):
        """
        Register the personal agent.
        :param model_client: The ChatCompletionClient to be used by the personal agent.
        :param model_clients: A dictionary containing the model to be used when processing pairing agents.
        The key is the name of the model and the value is the ChatCompletionClient.
        :return: None
        """
        await MyAgent.register(
            cls._get_instance(),
            "my_agent",
            lambda: MyAgent(
                model_client=model_client,
                processing_model_clients = model_clients
            )
        )

        print("My Agent Registered")

    @classmethod
    async def send_message(cls, message, agent_type, agent_key="default"):
        """
        Send a message to the specified agent type and key.
        :param message: The message to be sent.
        :param agent_type: The type of the agent to which the message is sent, either `my_agent` or `orchestrator_agent`.
        :param agent_key: The key of the agent to which the message is sent. By default, it is set to `default`.
        :return: None
        """
        instance = cls._get_instance()
        agent_id = AgentId(agent_type, agent_key)

        print(f"SENDING TO: {agent_id} the {message}")
        return await instance.send_message(message, agent_id)

    @classmethod
    async def get_agent_relations(cls, message) -> dict:
        """
        The method asks the orchestrator agent for the all the agent's relations and returns a dictionary containing them.
        :param message: The message to be sent to the orchestrator agent with the request type.
        :return: A dictionary containing the agent's relations.
        """
        instance = cls._get_instance()
        answer = await instance.send_message(message, AgentId("orchestrator_agent", "default"))
        return answer.agents_relation

    @classmethod
    async def get_registered_agents(cls, message) -> set[str]:
        """
        The method asks the orchestrator agent for the all the registered agents and returns a set containing them.
        :param message: A message containing the orchestrator request.
        :return: A set containing the usernames of the registered agents.
        """
        instance = cls._get_instance()
        answer = await instance.send_message(message, AgentId("orchestrator_agent", "default"))
        return answer.registered_agents

    @classmethod
    def configure_runtime(cls, model_type : ModelType, processing_model_clients : Dict[str, ChatCompletionClient],
                          model : str = None, temperature_my_agent : float = 0.5,
                          temperature_orchestrator : float = 0.5) -> None:
        """
        The method configures the runtime with the specified model type, processing model clients,
        model name, temperatures for the personal agent and the orchestrator agent.
        :param model_type: The model type or the specified model: Ollama, OpenAI, GEMINI or MISTRAL.
        :param processing_model_clients: The dictionary containing the model to be used when processing pairing agents.
        The key is the name of the model and the value is the ChatCompletionClient.
        :param model: The name of the model to be used.
        :param temperature_my_agent: The temperature of the LLM model to be used by the personal agent..
        :param temperature_orchestrator: The temperature of the LLM model to be used by the orchestrator agent.
        :return:
        """
        model_my_agent = get_model(model_type, model, temperature_my_agent)
        model_orchestrator = get_model(model_type, model, temperature_orchestrator)

        asyncio.run(Runtime.register_my_agent(model_client=model_my_agent, model_clients=processing_model_clients))
        asyncio.run(Runtime.register_orchestrator(model_client=model_orchestrator, model_client_name=model))


def get_model(model_type : ModelType, model : Optional[str] = None, temperature : float = 0.5) -> ChatCompletionClient:
    """
    The method returns the specified model client.
    :param model_type: The model type or the specified model: Ollama, OpenAI, GEMINI or MISTRAL.
    :param model: The name of the model to be used. If not specified, the default model is used.
    :param temperature: The temperature of the LLM model to be used. If not specified, the default temperature is used.
    :return: A ChatCompletionClient, an instance of the specified model.
    """
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

async def register_agents(model_client : ChatCompletionClient, model_name : str, model_clients : Dict[str, ChatCompletionClient]):
    """
    The method registers the personal agent and the orchestrator agent.
    :param model_client: A ChatCompletionClient, an instance of the specified model.
    :param model_name: the name of the model.
    :param model_clients: a dictionary containing the model to be used when processing pairing agents.
    :return: None
    """
    await Runtime.register_my_agent(model_client=model_client, model_clients=model_clients)
    await Runtime.register_orchestrator(model_client=model_client, model_client_name=model_name)

async def register_orchestrator(model_client : ChatCompletionClient, model_name : str):
    """
    The method registers the orchestrator agent.
    :param model_client: The ChatCompletionClient to be used by the orchestrator agent.
    :param model_name: The name of the model to be used by the orchestrator agent.
    :return: None
    """
    await Runtime.register_orchestrator(model_client=model_client, model_client_name=model_name)

async def register_my_agent(model_client : ChatCompletionClient, model_clients : Dict[str, ChatCompletionClient]):
    """
    The method registers the personal agent.
    :param model_client: The ChatCompletionClient to be used by the personal agent.
    :param model_clients: The dictionary containing the model to be used when processing pairing agents.
    :return: None
    """
    await Runtime.register_my_agent(model_client=model_client, model_clients=model_clients)

