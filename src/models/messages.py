from dataclasses import dataclass
from typing import Optional, Set, Dict

from .. import ActionType
from ..enums import (Relation, RequestType, AgentRelations_PersonalAgents, CompleteAgentRelations)


@dataclass
class SetupMessage:
    """
    Message sent by a user to after creating an account to setup the personal agent with the information the user sends as a natural language message in `content`.
    A value for the default policies to follow (to determine how strict they should be) could be selected. By default, no default policies will be applied.
    """
    content: str
    user: str
    default_value : int = -1

@dataclass
class ConfigurationMessage:
    """
    Message sent by an agent to the orchestration to forward the processed information the user first sent.
    """
    user: str
    user_information: dict
    user_policies: dict

@dataclass
class PairingRequest:
    """
    Message sent by the orchestrator to an agent containing a pairing request for an agent from another requester agent
    """
    requester: str
    requester_information: str
    feedback: str = ""
    receiver : str = ""

@dataclass
class PairingResponse:
    """
    Message sent by the personal agent to the orchestrator containing a response for a pairing request previously received.

    As the orchestrator is the agent sending the pairing request to the personal agent, the pairing response is the corresponding response
    to each pairing request received.
    """
    answer: dict[str, Relation]
    reasoning: str


@dataclass
class GetRequest:
    """
    Request to get information from the orchestrator's data structures.
    """
    request_type: RequestType
    user: str = ""

@dataclass
class ActionRequest:
    """
    Request to change the state of an agent following the type in `request_type`.
    """
    action_type: ActionType
    user: str = ""

@dataclass
class GetResponse:
    """
    Answer the orchestrator sends to the get requests it receives.
    """
    request_type: RequestType
    agents_relation: AgentRelations_PersonalAgents = None
    agents_relation_full: CompleteAgentRelations = None
    registered_agents: Set[str] = None
    users_and_public_info : Dict[str, str] = None
    models : dict[str, bool] = None

@dataclass
class UserInformation:
    """
    Message sent by the personal agent to the user with the personal information requested.
    """
    public_information: dict
    private_information: dict
    policies: dict
    username : str
    paused : bool = False
    is_setup : bool = True
    reset_connections : bool = False

@dataclass
class ModelUpdate:
    """
    Message sent to select the LLM to be used for the pairings
    """
    models : Dict[str, bool]

@dataclass
class InitMessage:
    """
    An empty message sent to create/init a MyAgent.
    The runtime sending this message to a non-existing agent will create it.
    """

@dataclass
class FeedbackMessage:
    """
    Message sent by a user to the orchestrator containing the feedback on an evaluated pairing.
    """
    sender : str
    receiver : str
    feedback: Relation

@dataclass
class AddServiceMessage:
    """
    Message sent to the Orchestrator containing a request to add a new service to the list of available services saved by the orchestrator.
    """
    name : str
    description : str
    website : str = ""

@dataclass
class GetServiceMessage:
    """
    Message sent by a personal agent to the Orchestrator on behalf of a user requesting a service from a natural language message describing
    the wanted task the service is needed for.
    Example: "I want to create a music playlist" -> Service to create a music playlist (Spotify, Apple Music, ...)
    """
    username : str
    description : str

@dataclass
class GetServiceAnswer:
    """
    Message sent by the Orchestrator as an answer to a previously received `GetServiceMessage`.
    """
    results : list[str]
    information : dict[str, str]