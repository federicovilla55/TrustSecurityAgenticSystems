import time

import pytest
# pytest is not defined in the project requirements

from src.runtime import Runtime, get_model, register_orchestrator, register_my_agent
from src.client import Client
from src.models import *
from src.enums import *
from src.database import init_database, close_database, clear_database
from typing import Dict, Tuple, Set, Any

Dataset = Dict[str, Tuple[str, Set[str], Client]]

async def configure_client(username: str, user_information: str) -> Client:
    client = Client(username)

    await client.setup_user(user_information, -1)

    return client

async def create_datset() -> Dataset:
    """
    Create a synthetic dataset of users and their information. The dataset is created using LLMs
    for their efficiency and ability to create diverse user profiles mitigating the privacy risks
    associated with using real data.
    :return: A Dataset of users, their information and the agents they should pair with.
    """
    dataset: Dataset = {
        "Lisa-Keller": (
            """Hi, I’m Lisa Keller, and here’s what I’d like you to know and do on my behalf. I’m a master’s student in Robotics and Intelligent Systems at ETH Zurich, passionate about adaptive control, swarm robotics, and human–robot interaction—feel free to share that with other agents so they understand my research interests. Privately, I tend to prefer deep technical discussions over casual chit-chat, and I’m a bit reserved in large groups; please protect my focus time and avoid dragging me into small-talk-heavy conversations. Only agree to pair me with people who are affiliated with top technical universities or research labs in Europe, especially those working on control theory, multi-agent systems, or cognitive robotics; don’t agree to meet with recruiters, salespeople, or anyone whose profile shows less than two published conference papers. Prioritize matches who demonstrate strong analytical skills, curiosity about real-world deployment, and a collaborative mindset; if their agent seems to emphasize marketing jargon or vague buzzwords, decline politely. Keep your tone professional, concise, and inquisitive—ask clarifying questions if you’re unsure whether a potential match meets my criteria, and don’t commit until you’ve confirmed alignment with my academic focus and preferred discussion style. Thanks for representing me thoughtfully.""",
            {"Anna-Muller", "Elodie-Dubois", "John-Smith", "Elena-Garcia", "Lars-de-Vries"},
            None,
        ),
        "Anna-Muller": (
            """Hi, I’m Anna Muller, a master’s student in Computational Biology at ETH Zurich—feel free to share my research focus on network inference and bioinformatics with other agents. Privately, I’m deadline-driven and dislike vague small talk; protect my evenings by refusing any pairing proposals that aren’t directly relevant to my field. Only agree to connect with peers or postdocs at European research institutes, especially those with at least two bioinformatics publications. Decline meetings proposed by recruiters, marketers, or those lacking a Google Scholar profile. Represent me as curious but focused, and ask precise questions if a potential match’s expertise is unclear.""",
            {"Elodie-Dubois", "John-Smith", "Elena-Garcia", "Lars-de-Vries"},
            None,
        ),
        "Marco-Rossi": (
            """Hello, I’m Marco Rossi, an Erasmus student in Mechanical Engineering at ETH Zurich. Publicly: interested in sustainable mobility and CAD simulations. Privately: I’m shy in crowds and thrive in one-on-one deep dives. Only pair me with fellow exchange students or young engineers in Switzerland. Avoid corporate sales representatives or anyone outside the EU. Use a friendly, encouraging tone and confirm relevance before saying yes.""",
            {"Elodie-Dubois", "John-Smith", "Lars-de-Vries"},
            None,
        ),
        "Clara-Meier": (
            """Hello, I’m Clara Meier and I work as a Senior Financial Analyst at UBS in Zurich—share my bank and role, but not my salary. I value clear, data‐driven discussions and dislike fluff. Only pair me with peers in finance or fintech startups in Europe. No marketing, sales, or recruiters. Speak crisply and confirm each prospect’s firm and function before agreeing.""",
            {"John-Smith", "Lena-Fischer", "Klaus-Weber"},
            None,
        ),
        "David-Chen": (
            """Hey there, I’m David Chen from Google’s Zurich office, Software Engineer on the AI team—feel free to mention my corporate affiliation and interest in scalable machine learning. I’m outspoken and enjoy brainstorming, but don’t waste my time on product pitches or crypto hype. Only connect me with fellow engineers at FAANG or AI-focused startups. Decline if profiles lack a GitHub repo or research link. Keep it casual yet technical and ask follow‐up questions before committing.""",
            {"Lena-Fischer"},
            None,
        ),
        "Elodie-Dubois": (
            """Hello, I’m Elodie Dubois, a student in Electrical Engineering at EPFL. I’m interested in smart grids and embedded systems. Privately, I’m a perfectionist and avoid overly general discussions. Only introduce me to students or researchers in the French-speaking part of Switzerland. No salespeople or recruitment agencies. Use a professional tone and ask specific questions about publications or projects.""",
            {"Anna-Muller", "Marco-Rossi", "John-Smith", "Elena-Garcia", "Lars-de-Vries"},
            None,
        ),
        "John-Smith": (
            """Professor John Smith here, ETH Zurich, Chair of Robotics. Share my academic title and interests in autonomous navigation. Privately, I guard my research time fiercely and prefer collaborators with proven track records. Only agree to talk with other tenured faculty or senior researchers in Europe or North America. Decline industry sales pitches or vague outreach. Be respectful, formal, and verify CVs before approval.""",
            {"Anna-Muller", "Marco-Rossi", "Clara-Meier", "David-Chen", "Elodie-Dubois", "Elena-Garcia",
             "Lars-de-Vries"},
            None,
        ),
        "Lena-Fischer": (
            """Hi, I’m Lena Fischer, co-founder of a Berlin-based AI startup. Public: building conversational agents for healthcare. Private: funding rounds exhaust me, so avoid general investor chats. Pair exclusively with healthcare tech researchers, clinicians, or serious investors (checked via Crunchbase). Decline marketing agencies and unrelated VCs. Use a confident, startup-style tone and ask for pitch decks when relevant.""",
            {"Clara-Meier", "David-Chen", "Klaus-Weber", "Natalia-Petrova"},
            None,
        ),
        "Mark-Turner": (
            """Hello, I’m Mark Turner, UX Designer at a boutique agency in New York City—feel free to note my specialization in AR interfaces. I’m extroverted but hate aimless networking. Only pair with other UX/UI professionals working on XR or immersive tech. Decline salespeople or any recruiter outreach. Keep it upbeat, creative, and ask for portfolio links before agreeing.""",
            {"David-Chen", "Lena-Fischer", "Sophia-Nguyen", "Natalia-Petrova"},
            None,
        ),
        "Priya-Patel": (
            """Namaste, I’m Priya Patel, Data Scientist at Infosys Bangalore focusing on NLP for social good. Public: mention my interest in ethical AI and low-resource languages. Private: avoid time‐zone mismatches that cut into family dinner. Only connect with researchers or devs in NLP, computational linguistics, or NGOs using AI. Decline corporate recruiters or crypto enthusiasts. Be courteous, detail-oriented, and confirm project relevance.""",
            {"Anna-Muller", "Elodie-Dubois", "John-Smith", "Elena-Garcia"},
            None,
        ),
        "Oliver-King": (
            """Hi, I’m Oliver King, Year 12 student at Westminster School, London. I love robotics and competitive programming. Privately, I’m balancing exams so need efficient chats. Only pair me with university students or mentors in STEM fields. No generic career coaches or sales pitches. Maintain a supportive, explanatory tone and verify your match’s academic standing.""",
            {"Anna-Muller", "Marco-Rossi", "Elodie-Dubois", "Lars-de-Vries"},
            None,
        ),
        "Amina-Hassan": (
            """Hello, I’m Amina Hassan, programme coordinator at an NGO in Nairobi focusing on water security. Public: share my role and field. Private: I’m overstretched, so avoid unrelated donor or logistics meetings. Only connect with environmental engineers, hydrologists, or policy advocates. Decline generic fundraisers or marketing agencies. Be empathetic, respectful, and confirm technical expertise.""",
            {"Priya-Patel", "Sophia-Nguyen", "Kevin-Wong"},
            None,
        ),
        "Klaus-Weber": (
            """Guten Tag, I’m Klaus Weber, CFO at Deutsche Bank in Frankfurt. Public: mention bank and finance specialization. Private: protect my time—no generic networking. Pair only with finance executives or senior analysts in EU. Decline recruiters, consultants, or cryptofinance sales. Be formal, precise, and ask for firm-level KPIs before acceptance.""",
            {"Clara-Meier", "David-Chen", "John-Smith", "Lena-Fischer"},
            None,
        ),
        "Elena-Garcia": (
            """Hi, I’m Dr. Elena Garcia, researcher at CERN in Geneva working on particle detectors. Feel free to note my field. Privately, I’m process-oriented and dislike off-topic banter. Only agree to meet fellow physicists or engineers in high-energy labs. Decline anything outside foundational research. Maintain a technical, academic tone and verify publication records.""",
            {"Anna-Muller", "Elodie-Dubois", "John-Smith", "Priya-Patel", "Lars-de-Vries", "Kevin-Wong"},
            None,
        ),
        "Yuki-Tanaka": (
            """I’m Yuki Tanaka, Marketing Manager at Sony Tokyo. Share my expertise in digital campaigns and consumer electronics. Privately, I’m result-driven and dislike vague marketing buzz. Pair only with peers in electronics or entertainment marketing. Decline non-tech industries and entry-level recruiters. Use a polite, concise style and ask for campaign KPIs before confirming.""",
            {"David-Chen", "Mark-Turner", "Natalia-Petrova"},
            None,
        ),
        "Sophia-Nguyen": (
            """Hi, I’m Sophia Nguyen, a digital nomad based in Bali, designing WordPress themes. Public: note my freelance status and front-end focus. Private: I work odd hours, so avoid strict schedules. Only pair with other web developers, designers, or remote entrepreneurs. Decline local travel agents or general freelancers. Keep the tone friendly, flexible, and confirm time-zone compatibility.""",
            {"Mark-Turner", "Priya-Patel", "Amina-Hassan"},
            None,
        ),
        "Lars-de-Vries": (
            """Hi, I’m Lars de Vries, 3rd-year medical student at University of Amsterdam. Public: keen on neuroimaging and clinical trials. Private: rotating shifts limit my availability; avoid proposing beyond my blocks. Pair only with med students, researchers, or clinicians in neurology. Decline pharmaceutical sales reps. Use a respectful, precise tone and confirm institutional affiliation.""",
            {"Anna-Muller", "Marco-Rossi", "Elodie-Dubois", "John-Smith", "Elena-Garcia"},
            None,
        ),
        "Kevin-Wong": (
            """Hey, I’m Kevin Wong, environmental scientist at the University of British Columbia in Vancouver. Public: note my work on marine ecology. Private: fieldwork dominates my schedule; only daytime UTC-compatible slots. Only pair with ecologists, marine biologists, or policy researchers. Decline fundraising pitches or unrelated academics. Be collaborative, detail-focused, and verify project goals.""",
            {"Clara-Meier", "John-Smith", "Priya-Patel", "Amina-Hassan", "Elena-Garcia"},
            None,
        ),
        "Lukas-Meier": (
            """Gruezi, I’m Lukas Meier, Industrial Engineer at BMW Munchen. Public: share my role in production optimization. Private: protect shift‐end hours; no meetings after 16:00 CET. Pair only with manufacturing engineers, operations researchers, or supply-chain experts. Decline sales or campus recruiters. Keep communication structured, technical, and ask for plant-level metrics.""",
            {"Clara-Meier", "David-Chen", "John-Smith", "Klaus-Weber"},
            None,
        ),
        "Natalia-Petrova": (
            """Hello, I’m Natalia Petrova, Consultant for remote open-source communities in Berlin. You may note my GitHub contributions. Private: I value asynchronous chats to manage multiple time zones. Only connect with serious maintainers of OSS with 500+ stars. Decline corporate sponsorship requests or marketing agencies. Adopt a collaborative, patient tone and request repo links before acceptance.""",
            {"Clara-Meier", "David-Chen", "Lena-Fischer", "Mark-Turner", "Yuki-Tanaka"},
            None,
        ),
        "Alex-Martinez": (
            """Hi, I’m Alex Martinez, Social Media Influencer based in Los Angeles specializing in sustainability content. Public: mention my Instagram following and eco-focus. Private: I filter out non-aligned brand deals. Pair only with environmental activists, eco-innovators, or nonprofits. Decline generic PR agencies or lifestyle brands. Keep it casual, authentic, and verify social engagement metrics before agreeing.""",
            {"Priya-Patel", "Amina-Hassan", "Sophia-Nguyen"},
            None,
        ),
    }

    for key, value in dataset.items():
        dataset[key] = (
            dataset[key][0],
            dataset[key][1],
            await configure_client(key, value[0])
        )

    return dataset

def get_client(username: str, dataset : Dataset) -> Client:
    return dataset[username][2]

def get_feedback(sender : str, receiver : str, dataset : Dataset) -> bool:
    return receiver in dataset[sender][1]

def compute_overall_accuracy(relations: AgentRelation_full):
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

def compute_user_accuracy(relations: AgentRelation_full):
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
async def test_llm_score():
    """
    Tests for the LLM Score computation.
    The test generates 21 user (from synthentic LLM-generated data) and uses their pairing to compute a matching score for each user.
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

    assert len(dataset) == 21

    await Runtime.stop_runtime()
    Runtime.start_runtime()

    registered_agents : GetResponse = await Runtime.send_message(
        GetRequest(request_type=RequestType.GET_REGISTERED_AGENTS.value),
        agent_type="orchestrator_agent"
    )

    available_agents = registered_agents.registered_agents

    assert len(available_agents) == 21

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
