from enum import Enum

class Relation(Enum):
    ACCEPTED = 1
    REFUSED = 2
    USER_REFUSED = 3
    USER_ACCEPTED = 4
    UNCONTACTED = 5

class RequestType(Enum):
    GET_AGENT_RELATIONS = 1
    GET_REGISTERED_AGENTS = 2
    GET_PERSONAL_RELATIONS = 3
    PAUSE_AGENT = 4
    RESUME_AGENT = 5
    DELETE_AGENT = 6

class ModelType(Enum):
    OLLAMA = 1
    OPENAI = 2
    GEMINI = 3
    MISTRAL = 4