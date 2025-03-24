# Trust and Security of Agentic Systems

## Project Overview

**PairMe via My Agent**: a multi-agent system application designed to study the trust, security and policy adherence in agentic frameworks.
Users create personalized agents with personal information they decide to give access to and policies for connecting to other agents.
Agents chat interact with each other and establish pairing for their humans in a two-phase process:
1. *Agent-to-Agent phase*: agents interact exchanging information their corresponding humans agree to share and follow defined rules.
2. *Human-in-the-Loop phase*: if agents agree to connect, humans approve or reject the meeting. In case they both accept, the agents set up a meeting for a convenient time.

The goal of the project is to evaluate: 
- how agent access personal information
- agents' policy based interactions
- their decision-making process
- human-in-the loop processes

--- 

## Installation

Clone and open the repository:
```bash
git clone https://github.com/federicovilla55/TrustSecurityAgenticSystems.git
cd TrustSecurityAgenticSystems
```

Install dependencies (*AutoGen requires Python 3.10 or later*)
```bash
pip install -r requirements.txt  
```

Run the Application:
```bash
python -m src.main
```

## Repository content

```bash
TrustSecurityAgenticSystems/
├── README.md
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── MyAgent.py
│   │   ├── OrchestratorAgent.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── messages.py
│   ├── runtime/
│   │   ├── __init__.py
│   │   ├── runtime.py
│   ├── enums/
│   │   ├── __init__.py
│   │   ├── enums.py
│   │   ├── custom_types.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── helpers.py
│   ├── main.py
│   ├── client.py
├── tests/
│   ├── __init__.py
│   ├── test_agent_implementation.py
```