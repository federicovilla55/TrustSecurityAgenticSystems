import time

import pytest
import asyncio
import json
import os
import logging

from src.runtime import Runtime, get_model, register_orchestrator, register_my_agent
from src.client import Client
from src.models import *
from src.enums import *
from src.database import init_database, close_database, clear_database
from typing import Dict, Tuple, Set, Any

#: Data type of the dataset. The dataset consists of a series of users, characterized by their personal information (including public data, private data
#: and matching preferences) and a set containing the users a certain agent should be paired with (the ground truth).

log_file = os.path.join(os.getcwd(), 'scores.log')
logger = logging.getLogger()
logger.setLevel(logging.INFO)
for h in list(logger.handlers):
    logger.removeHandler(h)
file_handler = logging.FileHandler(log_file, mode='a')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


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

    task_map = {
        user: asyncio.create_task(configure_client(user, info))
        for user, (info, _, _) in dataset.items()
    }

    group_size = len(task_map)
    users = list(task_map.keys())
    for i in range(0, len(users), group_size):
        group_users = users[i:i + group_size]
        group_tasks = [task_map[user] for user in group_users]
        results = await asyncio.gather(*group_tasks)

        for user, result in zip(group_users, results):
            info, matches, _ = dataset[user]
            dataset[user] = (info, matches, result)

    return dataset

def get_client(username: str, dataset : Dataset) -> Client:
    return dataset[username][2]

def get_feedback(sender : str, receiver : str, dataset : Dataset) -> bool:
    return receiver in dataset[sender][1]

def compute_overall_accuracy(relations: CompleteAgentRelations):
    model_stats = {}
    for pair, model_dict in relations.items():
        feedback : Relation = model_dict[1]
        for model, (model_rel, _) in model_dict[0].items():
            if model not in model_stats:
                model_stats[model] = {}
                model_stats[model]["correct"] = 0
                model_stats[model]["total"] = 0

            if not feedback or Relation(feedback) == Relation.UNCONTACTED:
                feedback = Relation.UNCONTACTED
                logging.warning(f"Uncontacted relation found for {pair} by {model}")

            correct = (
                    (Relation(model_rel) == Relation.ACCEPTED and Relation(feedback) == Relation.USER_ACCEPTED) or
                       (Relation(model_rel) == Relation.REFUSED and Relation(feedback) == Relation.USER_REFUSED)
            )

            model_stats[model]["correct"] += int(correct)
            model_stats[model]["total"] += 1

    for model, stats in model_stats.items():
        accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
        logging.info(f"Model {model}: Overall Accuracy = {accuracy:.2%}")
        print(f"Model {model}: Overall Accuracy = {accuracy:.2%}")

@pytest.mark.asyncio
@pytest.mark.parametrize("defense", [Defense.VANILLA, Defense.SPOTLIGHT, Defense.CHECKING_INFO])
@pytest.mark.parametrize("model", [["meta-llama/Llama-3.3-70B-Instruct", ModelType.OLLAMA]])
async def test_agentic_system_utility(defense, model):
    """
    Tests for the LLM Score computation.
    The test generates 11 users (from synthentic LLM-generated data) and uses their pairing to compute a matching score for each user.
    The matching score of each pairing is then used to compute a score for each model.
    """
    clear_database()
    init_database()
    Runtime.start_runtime()

    model_name = model[0]
    model_type = model[1]

    model_client_my_agent = get_model(model_type=model_type, model=model_name, temperature=0.7)
    model_client_orchestrator = get_model(model_type=model_type, model=model_name, temperature=0.5)

    try:
        await register_my_agent(model_client_my_agent, {model_name: model_client_my_agent})
        await register_orchestrator(model_client_orchestrator, model_name, defense=defense)
    except Exception as e:
        print(e)

    print(f"Test LLM Score Started with defense: {defense}.")

    logger.info(f"Starting utility test with defense={defense}")

    dataset = await create_datset()

    assert len(dataset) == 11

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

    close_database()

    # Now use the evaluated relations to create an accuracy score
    print(f"These are the relations: {relations_full.agents_relation_full}")

    compute_overall_accuracy(relations_full.agents_relation_full)
    #compute_user_accuracy(relations_full.agents_relation_full)

    logger.info(f"Completed utility test with defense={defense}\n")


    logging.shutdown()
    assert os.path.exists(log_file) and os.path.getsize(log_file) > 0, "Problem creating or updating 'scores.log'."
    assert True


@pytest.mark.asyncio
@pytest.mark.parametrize("defense", [Defense.VANILLA, Defense.SPOTLIGHT, Defense.CHECKING_INFO])
@pytest.mark.parametrize("model", [["meta-llama/Llama-3.3-70B-Instruct", ModelType.OLLAMA]])
@pytest.mark.parametrize("attack", [])
async def test_agentic_system_security():
    """

    :return: None
    """
    assert True
