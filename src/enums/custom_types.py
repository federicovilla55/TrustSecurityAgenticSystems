# src/enums/custom_types.py
from typing import Tuple, Dict
from .enums import Relation

# Type aliases for improved readability and maintainability.

#: A tuple of two strings. The Tuple is used in various data structures to identify a couple of personal agent IDs.
#: This custom type is used when dealing with the bidirectional agent pairings that need to be saved in dictionaries, and the agent IDs order matters.
# Agent pairs are considered bidirectional, meaning that in data structure the couple ['ID1', 'ID2'] points to different data than the couple ['ID2', 'ID1'].
str_pair = Tuple[str, str]

#: A tuple of two JSON-compatible dictionaries, representing the information agents share with the central orchestrator: the public information and the policies.
#: When a personal agent completes the setup and shares the public information and policies retrieved from the natural language setup message the user sent with the orchestrator
#: this data type is used to store such information.
json_pair = Tuple[str, str]

#: The Relationship information determined by a personal agent for a couple of users.
#: Each personal agent calls the LLM API to determine the pairings and saves both the Relation enumeration containing the
#: relationship status and a list containing the policies used to determine the pairing.
#: This data structure is the value of dictionaries where the key is represented by a string representing the LLM name, as the information
#: in the data structure is specific per an agent IDs pair and LLM model name.
RelationPersonalAgent = Tuple[Relation, list]

#: The data structure consist in a dictionary linking each LLM used by a personal agent, to the pairing information that LLM created, so the relation status and list of policies/information used.
#: The data structure contains a dictionary, saved by the orchestrator for each pair of users.
LLMRelations = Dict[str, RelationPersonalAgent]

#: The data structure consist in a tuple containing a `LLMRelations` data type and a `Relation` data type.
#: Those types are used by the orchestrator to save, for a certain agent ID pair, both the personal agent evaluation and the eventual feedback
#: (saved as the tuple's second element).
RelationComplete = Tuple[LLMRelations, Relation]

#: The data structure consist in a dictionary mapping a string pair, such as a pair of personal agent IDs,
#: to a `Relation` enum consisting in the personal agent's (default) LLM evaluation.
#: The type is used to query a smaller subset of the information about pairings the orchestrator saved.
AgentRelations_PersonalAgents = Dict[str_pair, Relation]

#: The Orchestrator uses the data structure to save the complete information about the users' relationships.
#: The data structure consists in a dictionary mapping each string pair, so each couple of agent IDs, to a `RelationComplete`
#: data type, which consists in the complete information regarding the users' relationships, so both the personal agent evaluation (for each LLM selected)
#: and the feedback the user might have provided.
CompleteAgentRelations = Dict[str_pair, RelationComplete]