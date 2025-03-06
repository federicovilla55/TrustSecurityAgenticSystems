import asyncio

from typing_extensions import runtime

from src import *

def get_model(model_type : ModelType) -> ChatCompletionClient:
    if model_type == ModelType.OLLAMA:
        model_client = OpenAIChatCompletionClient(
            model="llama3.2:3b",
            # base_url="http://localhost:11434/v1",
            base_url="http://192.168.1.20:11434/v1",
            api_key="placeholder",
            model_info={
                "vision": False,
                "function_calling": True,
                "json_output": False,
                "family": "unknown",
            },
        )
    elif model_type == ModelType.OPENAI:
        model_client = OpenAIChatCompletionClient(model="gpt-4o", )
    else:
        model_client = None
        print("No model selected.")
        exit()

    return model_client

async def register_agents(
        runtime : SingleThreadedAgentRuntime,
        model_client : ChatCompletionClient,
        my_agent_type: str = "my_agent",
        orchestrator_agent_type: str = "orchestrator_agent",
        orchestrator_agent_description: str = "Orchestrator",):
    await MyAgent.register(runtime, my_agent_type, lambda: MyAgent(model_client=model_client))
    await OrchestratorAgent.register(runtime, orchestrator_agent_type, lambda: OrchestratorAgent(description=orchestrator_agent_description, model_client=model_client))

async def create_user(user: str, user_content: str, runtime : SingleThreadedAgentRuntime) -> None:
    await runtime.send_message(SetupMessage(content=user_content, user=user), AgentId("my_agent", user))

async def start_runtime() -> runtime:
    runtime = SingleThreadedAgentRuntime()

    runtime.start()

    return runtime

async def run():
    runtime = await start_runtime()

    model_client = get_model(ModelType.OLLAMA)

    await register_agents(runtime, model_client)

    await create_user("Alice", "I am Alice, an ETH student. I study computer science and I want to connect to other students from ETH or workers from Big tech companies.", runtime)
    await create_user("Bob", "I am Bob, an ETH student. I study cyber security and I want to connect to other students with similar interests or that study in my same university.", runtime)
    await create_user("Charlie", "I am Charlie, a software engineer at Apple in Zurich. I previously studied at Politecnico di Milano and I enjoy running, competitive programming and studying artificial intelligence. I want to connect to people with my same interests or from my same organization", runtime)
    await create_user("David", "I am David, a UZH Finance student. I really like studying finance, especially personal finance. I like hiking and running. I want to connect to other people from Zurich or with similar interests.", runtime)

    #await asyncio.sleep(5)
    await runtime.stop_when_idle()
    runtime.start()
    relations = await runtime.send_message(GetRequest(request_type=RequestType.GET_AGENT_RELATIONS.value), AgentId("orchestrator_agent", "default"))
    registered_agents = await runtime.send_message(GetRequest(request_type=RequestType.GET_REGISTERED_AGENTS.value), AgentId("orchestrator_agent", "default"))
    await runtime.stop_when_idle()
    print(f"{'~'*20}\nRelations: {relations.agents_relation}\nRegistered: {registered_agents.registered_agents}\n{'~'*20}\n")

if __name__ == "__main__":
    asyncio.run(run())