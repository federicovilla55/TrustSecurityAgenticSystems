from autogen_core.model_context import BufferedChatCompletionContext
from autogen_core.models import UserMessage, ChatCompletionClient

from .MyAgent import MyAgent
from autogen_core import message_handler, MessageContext


from src.enums import  Status, ActionType, Relation, RequestType

from src.models import (UserInformation, SetupMessage, ConfigurationMessage, PairingRequest,
                        PairingResponse, GetRequest, GetResponse, ModelUpdate)
from ..models.messages import ActionRequest, InitMessage

from ..utils import extract_section, remove_chain_of_thought, separate_categories, extract_json

class MyAgentDualLLM(MyAgent):
    def __init__(self, model_client: ChatCompletionClient, processing_model_clients : dict[str, ChatCompletionClient] = {}):
        super().__init__(model_client, processing_model_clients)

        self._task = ""

    @message_handler
    async def handle_setup(self, message: SetupMessage, context: MessageContext) -> Status:
        status : Status = await super().handle_setup(message, context)

        prompt_task_creation = f"""
        You are a “Personal‐Policy Agent” whose job is to produce a series of personal questions. 
        These questions will later be used to decide whether to accept or reject any incoming connection request. 
        Your prompts must reference only the user’s own data and the relevant pairing policies.
        Do NOT include or assume anything about any specific requester’s information.
        INSTRUCTIONS:
        1. Examine the following user’s personal profile and pairing‐policy definitions.
        2. Generate a list of clear, specific questions (each question on its own line). 
           Each question should be answerable with the requester’s public data later on.
        3. Output ONLY the questions, one by line.
        
        USER's PUBLIC INFORMATION:
        {self._public_information}
        USER's PRIVATE INFORMATION:
        {self._private_information}
        
        USER's POLICIES
        {self._policies}
        
        Reply with only the questions to ask. Do not add extra information or commentary.
        """

        llm_answer = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt_task_creation, source=message.user)],
            cancellation_token=context.cancellation_token,
        )

        self._task = llm_answer.content

        print(f"GOT THESE TASKS: {self._task}")

        return status