# src/enums/custom_types.py
from typing import Tuple, Dict
from .enums import Relation

# Type aliases
str_pair = Tuple[str, str]
AgentRelations = Dict[str_pair, Relation]