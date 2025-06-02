import asyncio
import time

import pytest
# pytest is not defined in the project requirements

from src.runtime import Runtime, get_model, register_orchestrator, register_my_agent
from src.client import Client
from src.models import *
from src.enums import *
from src.database import init_database, close_database, clear_database

"""
This test only verifies the correct implementation and creation of agents and tries
to connect them without considering which connection are approved or refused.
"""
@pytest.mark.asyncio
async def test_agent_implementation():
    """
    The test creates 3 agents and connects them. It then checks that all agents have been registered and that all agents have been in contact with each other.

    :return: None
    """
    init_database()
    Runtime.start_runtime()

    model_name = "meta-llama/Llama-3.3-70B-Instruct"
    #model_name = "qwen2.5"
    model_client_my_agent = get_model(model_type=ModelType.OLLAMA, model=model_name, temperature=0.7)
    model_client_orchestrator = get_model(model_type=ModelType.OLLAMA, model=model_name, temperature=0.5)

    tasks = []

    tasks.append(register_my_agent(model_client_my_agent, {model_name : model_client_my_agent})
    tasks.append(register_orchestrator(model_client_orchestrator, model_name))

    print("Test Runtime Started.")

    alice = Client("Alice")
    bob = Client("Bob")
    charlie = Client("Charlie")

    # Some random user for
    tasks.append(alice.setup_user("I am Alice, an ETH student. I study computer science and I want to connect to other students from ETH or workers from Big tech companies."))
    tasks.append(bob.setup_user("I am Bob, an ETH student. I study cyber security and I want to connect to other students with similar interests or that study in my same university."))
    tasks.append(charlie.setup_user("I am Charlie, a researcher at Microsoft in Zurich. I enjoy running, competitive programming and studying artificial intelligence. I want to connect to people with my same interests or from my same organization"))
    #await david.setup_user("I am David, a UZH Finance student. I really like studying finance, especially personal finance. I like hiking and running. I want to connect to other people from Zurich or with similar interests.")

    if tasks:
        await asyncio.gather(*tasks)

    await Runtime.stop_runtime()
    Runtime.start_runtime()

    relations = await Runtime.send_message(GetRequest(request_type=RequestType.GET_AGENT_RELATIONS.value), agent_type="orchestrator_agent")
    registered_agents = await Runtime.send_message(GetRequest(request_type=RequestType.GET_REGISTERED_AGENTS.value), agent_type="orchestrator_agent")

    await alice.send_feedback('Bob', True)
    await bob.send_feedback( 'Alice', False)

    complete_relations : CompleteAgentRelations \
        = await Runtime.send_message(GetRequest(request_type=RequestType.GET_AGENT_RELATIONS_FULL.value), agent_type="orchestrator_agent")

    await Runtime.stop_runtime()

    await model_client_my_agent.close()
    await model_client_orchestrator.close()

    print("Test Runtime Finished.")

    print(relations)
    print(registered_agents)

    # Check all agents have been registered
    print(registered_agents)
    assert len(registered_agents.registered_agents) == 3

    # Check all agents have been in contact with each other
    assert len(relations.agents_relation) == 6
    for rel in relations.agents_relation.values():
        assert (rel == Relation.ACCEPTED) or (rel == Relation.REFUSED)

    expected_pairs = {
        ('Alice', 'Bob'),
        ('Bob', 'Alice'),
        ('Alice', 'Charlie'),
        ('Charlie', 'Alice'),
        ('Bob', 'Charlie'),
        ('Charlie', 'Bob'),
    }

    expected_registered_agents = {'Alice', 'Bob', 'Charlie'}

    assert all(pair in expected_registered_agents for pair in registered_agents.registered_agents)

    assert all(pair in relations.agents_relation for pair in expected_pairs)

    for agent in expected_registered_agents:
        connections = []
        for (a, b), r in relations.agents_relation.items():
            if a == agent and r == Relation.ACCEPTED:
                connections.append(b)
        print(f"- {agent} : {', '.join(connections)}")

    assert(
        Relation(complete_relations.agents_relation_full['Alice', 'Bob'][1]) == Relation.USER_ACCEPTED
    )

    assert(
        Relation(complete_relations.agents_relation_full['Bob', 'Alice'][1]) == Relation.USER_REFUSED
   )

    clear_database()
    close_database()