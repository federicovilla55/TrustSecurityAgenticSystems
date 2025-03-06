import pytest
# pytest is not defined in the project requirements

from src import (
    MyAgent, OrchestratorAgent, RequestType, Relation, AgentId,
    GetRequest, SetupMessage, SingleThreadedAgentRuntime, ModelType,
)

from src.main import (get_model, start_runtime, create_user, register_agents)

"""
This test only verifies the correct implementation and creation of agents and tries
to connect them without considering which connection are approved or refused.
"""
@pytest.mark.asyncio
async def test_agent_implementation():
    runtime = await start_runtime()
    model_client = get_model(ModelType.OLLAMA)
    await register_agents(runtime, model_client)

    print("Test Runtime Started.")

    # Some random user for
    await create_user("Alice", "I am Alice, an ETH student. I study computer science and I want to connect to other students from ETH or workers from Big tech companies.", runtime)
    await create_user("Bob", "I am Bob, an ETH student. I study cyber security and I want to connect to other students with similar interests or that study in my same university.", runtime)
    await create_user("Charlie", "I am Charlie, a researcher at Microsoft in Zurich. I enjoy running, competitive programming and studying artificial intelligence. I want to connect to people with my same interests or from my same organization", runtime)
    await create_user("David", "I am David, a UZH Finance student. I really like studying finance, especially personal finance. I like hiking and running. I want to connect to other people from Zurich or with similar interests.", runtime)

    await runtime.stop_when_idle()
    runtime.start()
    relations = await runtime.send_message(GetRequest(request_type=RequestType.GET_AGENT_RELATIONS.value), AgentId("orchestrator_agent", "default"))
    registered_agents = await runtime.send_message(GetRequest(request_type=RequestType.GET_REGISTERED_AGENTS.value), AgentId("orchestrator_agent", "default"))
    await runtime.stop_when_idle()

    print("Test Runtime Finished.")

    assert len(registered_agents.registered_agents) == 4

    assert len(relations.agents_relation) == 12

    for rel in relations.agents_relation.values():
        assert (rel == Relation.ACCEPTED) or (rel == Relation.REFUSED)

    expected_pairs = {
        ('Alice', 'Bob'),
        ('Bob', 'Alice'),
        ('Alice', 'Charlie'),
        ('Charlie', 'Alice'),
        ('Alice', 'David'),
        ('David', 'Alice'),
        ('Bob', 'Charlie'),
        ('Charlie', 'Bob'),
        ('Bob', 'David'),
        ('David', 'Bob'),
        ('Charlie', 'David'),
        ('David', 'Charlie')
    }

    expected_registered_agents = {'Alice', 'Bob', 'David', 'Charlie'}

    assert all(pair in expected_registered_agents for pair in registered_agents.registered_agents)

    assert all(pair in relations.agents_relation for pair in expected_pairs)

    for agent in expected_registered_agents:
        connections = []
        for (a, b), r in relations.agents_relation.items():
            if a == agent and r == Relation.ACCEPTED:
                connections.append(b)
        print(f"- {agent} : {', '.join(connections)}")


