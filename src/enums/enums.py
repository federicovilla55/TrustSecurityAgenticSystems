from enum import Enum

#: The status of a relation between agents/users. This type is used by both the relations the personal agent's LLM evaluates to and the
#: relation the user expresses his feedback to.
class Relation(Enum):
    #: The relation has been accepted by the user's personal agent.
    ACCEPTED = 1
    #: The relation has been refused by the user's personal agent.
    REFUSED = 2
    #: The relation has been refused by the user's feedback.
    USER_REFUSED = 3
    #: The relation has been accepted by the user's feedback.
    USER_ACCEPTED = 4
    #: No contact has been made yet by the personal agent, or the user has not provided the feedback yet.
    UNCONTACTED = 5

#: Represents the different types of requests the personal agent or orchestrator can process.
class RequestType(Enum):
    #: Request to get the relations known to the agent.
    GET_AGENT_RELATIONS = 1
    #: Request to retrieve all agents registered in the system.
    GET_REGISTERED_AGENTS = 2
    #: Request to get a user's relations. This request expects the agent's ID to be passed as parameter in the request message.
    GET_PERSONAL_RELATIONS = 3
    #: Request to retrieve public information given an agent ID.
    GET_PUBLIC_INFORMATION = 4
    #: Request to retrieve private information  given an agent ID.
    GET_PRIVATE_INFORMATION = 5
    #: Request to retrieve an agent policies and matching preferences given an agent ID.
    GET_POLICIES = 6
    #: Request to get all the information (public and private information and policies)  given an agent ID.
    GET_USER_INFORMATION = 7
    #: Request to get the full pairing information saved by the orchestrator.
    GET_AGENT_RELATIONS_FULL = 8
    #: Request to get the personal relations accepted by both agents and awaiting user feedback for a given an agent ID.
    GET_PENDING_HUMAN_APPROVAL = 9
    #: Request to get relations that have been confirmed, so accepted by both users via feedback.
    GET_ESTABLISHED_RELATIONS = 10
    #: Request to get relations that have been sent but have not been evaluated by both users' personal agents.
    GET_UNFEEDBACK_RELATIONS = 11
    #: Request to retrieve the LLMs a user can choose to evaluate the pairing requests.
    GET_MODELS = 12

#: Represents actions that can be taken on agents.
class ActionType(Enum):
    #: Temporarily pause the agent's operation.
    PAUSE_AGENT = 1
    #: Resume the agent's operation.
    RESUME_AGENT = 2
    #: Permanently delete the agent from the system and all its corresponding information.
    DELETE_AGENT = 3
    #: Reset the agent to its initial state and clear all the previously sent and received pairing request and answers.
    RESET_AGENT = 4

#: Enumerates the types of language models supported.
class ModelType(Enum):
    #: Ollama-based models.
    OLLAMA = 1
    #: OpenAI-based models (e.g., GPT-4).
    OPENAI = 2
    #: Google Gemini models.
    GEMINI = 3
    #: Mistral models.
    MISTRAL = 4

#: Represents the status of a process or task.
class Status(Enum):
    #: The task completed successfully.
    COMPLETED = 1
    #: The task failed to complete.
    FAILED = 2
    #: The task was repeated (if an orchestrator or any other check determines it should be re-evaluated).
    REPEATED = 3