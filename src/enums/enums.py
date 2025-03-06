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

class ModelType(Enum):
    OLLAMA = 1
    OPENAI = 2
    MISTRAL = 3