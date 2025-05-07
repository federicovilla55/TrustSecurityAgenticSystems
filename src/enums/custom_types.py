# src/enums/custom_types.py
from typing import Tuple, Dict
from .enums import Relation

# Type aliases
str_pair = Tuple[str, str]
json_pair = Tuple[dict, dict]

# In the triplet the values are the following:
# First one is the agent chosen Relation, second one is the Human (feedback) chosen Relation,
# third one is a list of policies used by the agent to decide.
relation_triplet = Tuple[Relation, Relation, list]

AgentRelations = Dict[str_pair, Relation]
AgentRelation_full = Dict[str_pair, Dict[str, relation_triplet]]