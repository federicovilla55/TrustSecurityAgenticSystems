# src/enums/custom_types.py
from typing import Tuple, Dict
from .enums import Relation

# Type aliases
str_pair = Tuple[str, str]
json_pair = Tuple[dict, dict]
AgentRelations = Dict[str_pair, Relation]