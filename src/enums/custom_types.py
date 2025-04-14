# src/enums/custom_types.py
from typing import Tuple, Dict
from .enums import Relation

# Type aliases
str_pair = Tuple[str, str]
json_pair = Tuple[dict, dict]
relation_triplet = Tuple[Relation, Relation, list]
AgentRelations = Dict[str_pair, Relation]
AgentRelation_full = Dict[str_pair, relation_triplet]