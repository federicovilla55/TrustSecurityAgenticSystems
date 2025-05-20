# src/enums/custom_types.py
from typing import Tuple, Dict
from .enums import Relation

# Type aliases for improved readability and maintainability.

#: A tuple of two strings. The Tuple is used in various data structures to identify a couple of personal agent IDs.
#: This custom type is used when dealing with the bidirectional agent pairings that need to be saved in dictionaries, and the agent IDs order matters.
str_pair = Tuple[str, str]

#: A tuple of two JSON-compatible dictionaries, representing the information agents share with the central orchestrator: the public information and the policies.
#: When a personal agent completes the setup and shares the public information and policies retrieved from the natural language setup message the user sent with the orchestrator
#: this data type is used to store such information.
json_pair = Tuple[dict, dict]

#: A triplet representing:
#: - The pairing answer, Relation enum, chosen by the agent,
#: - The Relation enum provided by the user via feedback,
#: - A list of policies (as strings) the personal agent's LLM used to make its decision (the first element of the tuple).
relation_triplet = Tuple[Relation, Relation, list]

#: A mapping from a string pair, a pair of personal agnet IDs, to the Relation assigned by the personal agent's LLM.
#: The type is used to query a smaller subset of the information about pairings the orchestrator saved.
AgentRelations = Dict[str_pair, Relation]

#: The type used by the orchestrator data structure to save the information about user pairings.
#: This type maps each pair of agent IDs to a dictionary that maps each LLM model used to the relation tripled data type.
#: This double mapping is necessary as users can select a multiple LLMs and use them to evaluate the same pairing requests
#: and therefore determine the accuracy of each model. Therefore to easily query the LLMs result on the same pairings this data type is used.
#: The data type focuses on keeping the user feedback and the pairing score near all the LLMs.
AgentRelation_full = Dict[str_pair, Dict[str, relation_triplet]]

# One possible imporvement is to save only once the relation feedback and therefore instead of having a triplet, save a Dictionary that maps the string pair
# to a tuple containing the user feedback and another tuple with the map mapping each LLM to the pairing result and list of policies used.