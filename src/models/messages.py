from dataclasses import dataclass
from typing import Optional, Set

from .. import ActionType
from ..enums import (Relation, RequestType, AgentRelations, AgentRelation_full)


@dataclass
class SetupMessage:
    """
    Message sent by a user to after creating the account to setup
    his agent with the information the user sends and the preferences for pairing other agents
    """
    content: str
    user: str

@dataclass
class ConfigurationMessage:
    """
    Message sent by an agent to the orchestration to forward the processed information the user first sent
    """
    user: str
    user_information: dict
    user_policies: dict

@dataclass
class PairingRequest:
    """
    Message sent by the orchestrator to an agent containing a pairing request for an agent
    from another requester agent
    """
    requester: str
    requester_information: str
    feedback: str = ""

@dataclass
class PairingResponse:
    """
    Message sent by the orchestrator an agent to the orchestrator containing a response
    for a pairing request
    """
    answer: Relation
    reasoning: str


@dataclass
class GetRequest:
    """
    Request to get information from the orchestrator's data
    """
    request_type: RequestType
    user: str = ""

@dataclass
class ActionRequest:
    """
    Request to get information from the orchestrator's data
    """
    request_type: ActionType
    user: str = ""

@dataclass
class GetResponse:
    """
    Answer to the orchestrator get request
    """
    request_type: RequestType
    agents_relation: AgentRelations = None
    agents_relation_full: AgentRelation_full = None
    registered_agents: Set[str] = None
    # more types should be added when the orchestrator will contain more information

@dataclass
class UserInformation:
    """
    Message sent by the MyAgent, the personal agent, to the user
    """
    public_information: dict
    private_information: dict
    policies: dict
    is_setup : bool = True

@dataclass
class InitMessage:
    """
    Message sent to create a MyAgent
    """

@dataclass
class FeedbackMessage:
    """
    Message sent by a user to the orchestrator containing the feedback on an evaluated connection.
    """
    sender : str
    receiver : str
    feedback: Relation