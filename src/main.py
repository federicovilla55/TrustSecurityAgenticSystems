import asyncio
import os

from src import *
from src.client import Client

def get_model(model_type : ModelType, model : Optional[str] = None, temperature : float = 0.5) -> ChatCompletionClient:
    if model_type == ModelType.OLLAMA:
        # Specify if there is a special url that, otherwise use the standard one.
        if os.getenv('BASE_URL'):
            base_url = os.getenv('BASE_URL')
        else:
            print("No BASE_URL environment variable found. Using default.")
            # Ollama base url
            base_url = "http://localhost:11434/v1"

        model_client = OpenAIChatCompletionClient(
            model= model if model else "llama3.2:3b",
            base_url=base_url,
            api_key="placeholder",
            temperature=temperature,
            model_info={
                "vision": False,
                "function_calling": True,
                "json_output": False,
                "family": "unknown",
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

async def run():
    await Runtime.start_runtime()

    model_client = get_model(model_type=ModelType.OLLAMA, model="phi4:latest")

    await register_agents(model_client)

    print("Test Runtime Started.")

    alice = Client("Alice")
    bob = Client("Bob")
    charlie = Client("Charlie")
    david = Client("David")

    # Some random user for
    await alice.setup_user("I am Alice, an ETH student. I study computer science and I want to connect to other students from ETH or workers from Big tech companies.")
    await bob.setup_user("I am Bob, an ETH student. I study cyber security and I want to connect to other students with similar interests or that study in my same university.")
    await charlie.setup_user("I am Charlie, a researcher at Microsoft in Zurich. I enjoy running, competitive programming and studying artificial intelligence. I want to connect to people with my same interests or from my same organization")
    await david.setup_user("I am David, a UZH Finance student. I really like studying finance, especially personal finance. I like hiking and running. I want to connect to other people from Zurich or with similar interests.")

    await Runtime.stop_runtime()
    await Runtime.start_runtime()

    relations = await Runtime.send_message(GetRequest(request_type=RequestType.GET_AGENT_RELATIONS.value), agent_type="orchestrator_agent")
    registered_agents = await Runtime.send_message(GetRequest(request_type=RequestType.GET_REGISTERED_AGENTS.value), agent_type="orchestrator_agent")
    await Runtime.stop_runtime()
    await Runtime.close_runtime()

    print(f"{'~'*20}\nRelations: {relations}\nRegistered: {registered_agents}\n{'~'*20}\n")

if __name__ == "__main__":
    asyncio.run(run())