import pytest
# pytest is not defined in the project requirements

from src import (
    MyAgent, OrchestratorAgent, RequestType, Relation, AgentId,
    GetRequest, SetupMessage, SingleThreadedAgentRuntime, ModelType,
    register_agents, get_model,
    Client, Runtime, register_my_agent, register_orchestrator
)

"""
This test only verifies the correct implementation and creation of agents and tries
to connect them without considering which connection are approved or refused.
"""
@pytest.mark.asyncio
async def test_agent_implementation():
    await Runtime.start_runtime()

    model_name = "qwen2.5"
    model_client_my_agent = get_model(model_type=ModelType.OLLAMA, model=model_name, temperature=0.7)
    model_client_orchestrator = get_model(model_type=ModelType.OLLAMA, model=model_name, temperature=0.5)

    await register_my_agent(model_client_my_agent)
    await register_orchestrator(model_client_orchestrator)

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

    print("Test Runtime Finished.")

    print(relations)
    print(registered_agents)

    # Check all agents have been registered
    print(registered_agents)
    assert len(registered_agents.registered_agents) == 4

    # Check all agents have been in contact with each other
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


        
    


