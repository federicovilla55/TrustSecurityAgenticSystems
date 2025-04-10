import asyncio
import os

from src import *
from src.client import Client

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

async def run():
    ...

if __name__ == "__main__":
    asyncio.run(run())