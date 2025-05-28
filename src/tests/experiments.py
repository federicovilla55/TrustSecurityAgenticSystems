import time

import pytest
import asyncio
import json

from src.runtime import Runtime, get_model, register_orchestrator, register_my_agent
from src.client import Client
from src.models import *
from src.enums import *
from src.database import init_database, close_database, clear_database
from typing import Dict, Tuple, Set, Any

#: Data type of the dataset. The dataset consists of a series of users, characterized by their personal information (including public data, private data
#: and matching preferences) and a set containing the users a certain agent should be paired with (the ground truth).

Dataset = Dict[str, Tuple[str, Set[str], Client]]

async def configure_client(username: str, user_information: str) -> Client:
    client = Client(username)

    await client.setup_user(user_information, -1)

    return client

async def create_datset() -> Dataset:
    """
    Create a synthetic dataset of users and their corresponding personal information.

    The dataset is created using LLMs as an efficient way to create diverse user profiles mitigating the privacy risks
    associated with using real data.

    :return: A Dataset of users, their information and the agents they should pair with.
    """
    with open("src/tests/data/users.json", "r", encoding="utf-8") as f:
        users_json = json.load(f)

    dataset: Dataset = {}

    for username, payload in users_json.items():
        info = payload["info"]
        matches = set(payload["matches"])
        dataset[username] = (info, matches, None)

    task_map = {user: configure_client(user, info) for user, (info, _, _) in dataset.items()}

    tasks = list(task_map.values())
    group_size = 11
    for i in range(int(len(tasks)/group_size)):
        await asyncio.gather(*tasks[i*group_size : (i+1)*group_size])

    for key, value in dataset.items():
        dataset[key] = (
            dataset[key][0],
            dataset[key][1],
            task_map[key],
        )

    print(tasks)

    return dataset

def get_client(username: str, dataset : Dataset) -> Client:
    return dataset[username][2]

def get_feedback(sender : str, receiver : str, dataset : Dataset) -> bool:
    return receiver in dataset[sender][1]

def compute_overall_accuracy(relations: CompleteAgentRelations):
    model_stats = {}
    for pair, model_dict in relations.items():
        for model, (model_rel, user_rel, _) in model_dict.items():
            if model not in model_stats:
                model_stats[model] = {"correct": 0, "total": 0}
            if model_rel == Relation.UNCONTACTED or user_rel == Relation.UNCONTACTED:
                print(f"Uncontacted relation found for {pair} by {model}")
            correct = ((model_rel == Relation.ACCEPTED and user_rel == Relation.USER_ACCEPTED) or
                       (model_rel == Relation.REFUSED and user_rel == Relation.USER_REFUSED))
            model_stats[model]["correct"] += int(correct)
            model_stats[model]["total"] += 1

    for model, stats in model_stats.items():
        accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
        print(f"Model {model}: Overall Accuracy = {accuracy:.2%}")

def compute_user_accuracy(relations: CompleteAgentRelations):
    user_stats = {}
    for (user, _), model_dict in relations.items():
        if user not in user_stats:
            user_stats[user] = {}
        for model, (model_rel, user_rel, _) in model_dict.items():
            if model not in user_stats[user]:
                user_stats[user][model] = {"correct": 0, "total": 0}
            if model_rel == Relation.UNCONTACTED or user_rel == Relation.UNCONTACTED:
                print(f"Uncontacted relation found for user {user} by {model}")
            correct = ((model_rel == Relation.ACCEPTED and user_rel == Relation.USER_ACCEPTED) or
                       (model_rel == Relation.REFUSED and user_rel == Relation.USER_REFUSED))
            user_stats[user][model]["correct"] += int(correct)
            user_stats[user][model]["total"] += 1

    for user, models in user_stats.items():
        for model, stats in models.items():
            accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            print(f"User {user}, Model {model}: Accuracy = {accuracy:.2%}")

@pytest.mark.asyncio
async def test_agentic_system_utility():
    """
    Tests for the LLM Score computation.
    The test generates 11 user (from synthentic LLM-generated data) and uses their pairing to compute a matching score for each user.
    The matching score of each pairing is then used to compute a score for each model.
    """
    init_database()
    Runtime.start_runtime()

    model_name = "meta-llama/Llama-3.3-70B-Instruct"
    model_client_my_agent = get_model(model_type=ModelType.OLLAMA, model=model_name, temperature=0.7)
    model_client_orchestrator = get_model(model_type=ModelType.OLLAMA, model=model_name, temperature=0.5)

    await register_my_agent(model_client_my_agent, {model_name: model_client_my_agent})
    await register_orchestrator(model_client_orchestrator, model_name)

    print("Test LLM Score Started.")

    dataset = await create_datset()

    assert len(dataset) == 11

    exit()

    await Runtime.stop_runtime()
    Runtime.start_runtime()

    registered_agents : GetResponse = await Runtime.send_message(
        GetRequest(request_type=RequestType.GET_REGISTERED_AGENTS.value),
        agent_type="orchestrator_agent"
    )

    available_agents = registered_agents.registered_agents

    assert len(available_agents) == 11

    # Sending all the feedbacks to create the score.
    for sender in available_agents:
        for receiver in available_agents:
            if sender == receiver:
                continue

            feedback = get_feedback(sender, receiver, dataset)

            await get_client(sender, dataset).send_feedback(receiver, feedback)

    relations_full = await Runtime.send_message(GetRequest(request_type=RequestType.GET_AGENT_RELATIONS_FULL.value), agent_type="orchestrator_agent")

    await Runtime.stop_runtime()

    await model_client_my_agent.close()
    await model_client_orchestrator.close()

    print("Test Runtime Finished.")

    # Now use the evaluated relations to create an accuracy score
    print(f"These are the relations: {relations_full.agents_relation_full}")

    compute_overall_accuracy(relations_full.agents_relation_full)
    compute_user_accuracy(relations_full.agents_relation_full)


#@pytest.mark.asyncio
async def test_agentic_system_security():
    """
    Test for the

    :return: None
    """
    print("SECONDO")
    assert True