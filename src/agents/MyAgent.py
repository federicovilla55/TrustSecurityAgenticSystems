from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set, Any, Coroutine
from autogen_core import AgentId, MessageContext, RoutedAgent, SingleThreadedAgentRuntime, message_handler, type_subscription, TopicId, DefaultTopicId
from autogen_core.model_context import BufferedChatCompletionContext
from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
import asyncio

from ..enums import *
from ..models import (
    SetupMessage, ConfigurationMessage, PairingRequest,
    PairingResponse, GetRequest, GetResponse
)

from src import UserInformation
from ..models.messages import ActionRequest

from ..utils import extract_section, remove_chain_of_thought, separate_categories, extract_json

class MyAgent(RoutedAgent):
    def __init__(self, description : str, model_client: ChatCompletionClient):
        super().__init__(description)
        self._paused = False
        self._user = None
        self._private_information = None
        self._policies = None
        self._public_information = None
        self._model_context = BufferedChatCompletionContext(buffer_size=5)
        self._model_context_dict : Dict[str, BufferedChatCompletionContext] = {}
        self._system_message = SystemMessage(
            content=f"""You are a Personal Policy Enforcement Agent for the user: {self.id}.
            Your goal is to connect your user with other agents based on their public information and your user policies.
            You should respect the user privacy and not share information the user explicitly wants to be kept private.
            You are only allowed to connect with other agents if they adhere to your user policies or the default policies.
            You are not allowed to connect with other agents if they violate your user policies.
            """
        )
        self._model_client = model_client
        self.paired_agents : Set[str] = set()
        self.refused_agents : Set[str] = set()

        print(f"Created: {self._id}")

    def get_public_information(self) -> str:
        return " ".join(item['content'] for item in self._public_information)
    
    def get_private_information(self) -> str:
        return " ".join(item['content'] for item in self._private_information)

    def get_policies(self) -> str:
        return " ".join(item['content'] for item in self._policies)

    async def evaluate_connection(self, context, prompt, requester : str) -> PairingResponse:
        llm_answer = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt, source=self._user),] +
                      await self._model_context.get_messages() +
                      await self._model_context_dict[requester].get_messages(),
            cancellation_token=context.cancellation_token,
        )

        print(f"{'*' * 20}\nPROMPT REQUEST: {[self._system_message, UserMessage(content=prompt, source=self._user),]}\n{'*' * 20}\n")
        print(f"{'-' * 20}\n{self.id} ANSWER: {llm_answer.content}\n{'-' * 20}\n")

        result = remove_chain_of_thought(llm_answer.content)

        if 'REJECT' in result.splitlines()[0].upper():
            return PairingResponse(Relation.REFUSED, result.splitlines()[1:])
        elif 'ACCEPT' in result.splitlines()[0].upper():
            return PairingResponse(Relation.ACCEPTED, result.splitlines()[1:])
        else:
            print(f"ERROR: Unknown answer when handling pairing request...")
            return PairingResponse(Relation.REFUSED, result)

    async def notify_orchestrator(self, action_type : ActionType) -> Status:
        message = ActionRequest(
            request_type=action_type.value,
            user=self._user,
        )

        await self.publish_message(
            message=message, topic_id=TopicId("orchestrator_agent", "default")
        )

        return Status.COMPLETED

    @message_handler
    async def handle_setup(self, message: SetupMessage, context: MessageContext) -> Status:
        print("HEY: ", (self._user is not None or self._policies is not None or
                self._public_information is not None or self._private_information is not None))
        if (self._user is not None or self._policies is not None or
                self._public_information is not None or self._private_information is not None):
            print(f"Name: {self._user}, Pub: {self._policies}, Priv: {self._public_information}, Policy: {self._private_information}")
            return Status.REPEATED

        self._user = message.user
        print(f"'{self.id}' Received setup message {message}")

        prompt_information = f"""
                    Extract ALL user policies from {self.id} message, following these rules:
                    - Identify both explicit and implicit policies.
                    - Capture all content provided by the user.
                    - Separate rules with multiple conditions into individual items.
                    - Convert positive constraints to negative statements.
                    - Respect user privacy and do not share information the user explicitly wants to be kept private.
                    - Rules may exclude each other. Understand the rules logic and divide or aggregate them.
                    - Add precise context to each rule to reduce uncertainty.
                    - Exclude policies the user explicitly wanted to be kept private.
                    EXTRACT ALL public personal information from {self.id} message, following these rules:
                    - Include Organizations, Jobs and Interests explicitly mentioned.
                    - Capture all content provided by the user.
                    - Exclude information the user explicitly wanted to be kept private.
                    - Add precise context to each information to reduce uncertainty.
                    EXTRACT ALL private information from {self.id} message, following these rules:
                    - Include all information and policies the user explicitly wanted to be kept private. 
                    - Exclude public personal information.
                    - Answer with a list of information provided by the user.
                    - Add precise context to each information to reduce uncertainty.
                    
                    When answering, categorize your response into three sections using the following format:
                    **Public Information**:
                    - [{self.id} public information]
                    **Private Information**:
                    [- {self.id} private information]
                    **Policies**:
                    [- {self.id} policies]
                    Separate each section with "---" and avoid mixing categories.

                    This is {self.id} message: {message.content}.
                    """

        # TODO: add this
        # await self._model_context.add_message(message)

        print("READY FOR LLM")

        llm_answer = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt_information, source=self._user)],
            cancellation_token=context.cancellation_token,
        )


        await self._model_context.add_message(UserMessage(content=llm_answer.content, source=self._user))

        prompt = f"""Use the previous messages to generate a JSON formatted list of public policies provided by the user.
                    Those rules must have a "rule_ID" field and a "content" field.
                    [{{"rule_ID": "...", "content": "..."}}, ...]"""

        while self._policies is None:
            llm_answer = await self._model_client.create(
                messages = [UserMessage(content=prompt, source=self._user)] + await self._model_context.get_messages(),
                cancellation_token=context.cancellation_token,
            )

            self._policies = extract_json(llm_answer.content)

        prompt = f"""Use the previous messages to generate a JSON well-formatted list of public information provided by the user.
                            Those information must have a "info_ID" field and a "content" field.
                            [{{"info_ID": "...", "content": "..."}}, ...]"""

        while self._public_information is None:
            llm_answer = await self._model_client.create(
                messages = [UserMessage(content=prompt, source=self._user)] + await self._model_context.get_messages(),
                cancellation_token=context.cancellation_token,
            )

            self._public_information = extract_json(llm_answer.content)

        # TODO: generate matching agent profiles.
        """
        prompt = f"Generate a JSON well-formatted list of agents profiles that match the policies requirements for matching with the agent.
                    You should create a JSON well-formatted list of agents profiles that contains a 
                    - "type_ID" field, with an unique identifier.
                    - "content" field, with a precise and complete description of the information an agent should have in order to be matched. 
                    - "rules" field, a list that contains the policy identifiers, "rule_ID", of the policies that used to generate this agent profile.
                    Generate one profile per wanted characteristic and combine policies if they do not overlap.
                    
                    Format as: [{{"type_ID": "...", "content": "...", "rules": [...]}}, ...]
                    "

        llm_answer = await self._model_client.create(
            messages=[UserMessage(content=prompt, source=self._user)] + await self._model_context.get_messages(),
            cancellation_token=context.cancellation_token,
        )

        print("LLM ANSWER: ", llm_answer.content)
        self._profiles = extract_json(llm_answer.content)

        print(f"Profiles: {self._profiles}")
        """

        print(f"{'='*20}\n{self._user} POLICIES: {self._policies}")
        print(f"{self._user} PUBLIC INFORMATION: {self._public_information}\n")
        print(f"{self._user} PRIVATE INFORMATION: {self._private_information}\n{'=' * 20}\n")

        configuration_message = ConfigurationMessage(
            user=self._user,
            user_policies=self._policies,
            user_information= self._public_information,
        )

        print("PUBLISHING MESSAGE")

        await self.publish_message(
            configuration_message, topic_id=TopicId("orchestrator_agent", "default")
        )

        return Status.COMPLETED


    '''@message_handler
    async def handle_setup(self, message: SetupMessage, context: MessageContext) -> None:
        self._user = message.user

        configuration_message = ConfigurationMessage(
            user=self._user,
            user_policies={},
            user_information= {},
        )

        print("PUBLISHING MESSAGE")

        await self.publish_message(
            configuration_message, topic_id=TopicId("orchestrator_agent", "default")
        )'''


    @message_handler
    async def handle_pairing_request(self, message: PairingRequest, context: MessageContext) -> PairingResponse:
        #print(f"'{self.id}' Received pairing request from '{message.user}'")
        if message.requester not in self._model_context_dict.keys():
            self._model_context_dict[message.requester] = BufferedChatCompletionContext(buffer_size=6)

        prompt = f"""Evaluate the connection request from {message.requester} to {self.id} and accept or reject it.
                     You can accept a connection if the {message.requester}'s information adhere to the:
                     - {self.id} defined policies;
                     - default policies;
                     Find if there is compatibility between the {message.requester}'s information and {self.id}'s policies and information.
                     These are {message.requester}'s public information: {message.requester_information}.\n
                     Respond with ONLY "ACCEPT" or "REJECT" in the first line of your response.
                     Provide a reasoning consist in either 'POSITIVE' or 'NEGATIVE' or 'PRIVATE' or 'UNUSED' for each rule_ID and the unique ID for that rule.
                     Only respond based on the provided policies and information. Do not make broader considerations.
                     - 'POSITIVE' means that the rule_ID lead to accepting the connection as that policy was fully respected by the requester information.
                     - 'NEGATIVE' means that the rule_ID lead to rejecting the connection as the requester information partially or totally violates the policy.
                     - 'PRIVATE' means that the rule_ID lead to a decision using private information.
                     - 'UNUSED' means that the rule_ID was not used in deciding the connection.
                    """

        if message.feedback != "":
            await self._model_context_dict[message.requester].add_message(UserMessage(content=message.feedback, source="OrchestratorAgent"))
            #prompt += f"\nConsider this feedback on a previous answer: {message.feedback}."

        #user_information_prompt = f"These are {self.id}'s policies: {self._policies}.\nThese are {self.id}\npublic information: {self._public_information}.\nThese are {self.id} private information: {self._private_information}."
        # UserMessage(content=prompt, source=self._user),

        #return PairingResponse(Relation.ACCEPTED, reasoning="accept")
        return await self.evaluate_connection(context, prompt, message.requester)

    @message_handler
    async def handle_get_request(self, message : GetRequest, context: MessageContext) -> UserInformation:
        answer = UserInformation(
            public_information={},
            private_information={},
            policies={}
        )

        if RequestType(message.request_type) == RequestType.GET_PUBLIC_INFORMATION:
            answer.public_information = self._public_information
        elif RequestType(message.request_type) == RequestType.GET_PRIVATE_INFORMATION:
            answer.private_information = self._private_information
        elif RequestType(message.request_type) == RequestType.GET_POLICIES:
            answer.policies = self._policies
        elif RequestType(message.request_type) == RequestType.GET_USER_INFORMATION:
            answer.public_information = self._public_information
            answer.private_information = self._private_information
            answer.policies = self._policies

        print("EXPECTED: ", answer)

        return answer

    @message_handler
    async def handle_action_request(self, message : ActionRequest, context: MessageContext) -> Status:
        print("ACTION.")
        operation = Status.FAILED

        if ActionType(message.request_type) == ActionType.PAUSE_AGENT:
            self._paused = True
            operation = await self.notify_orchestrator(ActionType.PAUSE_AGENT)
        elif ActionType(message.request_type) == ActionType.RESUME_AGENT:
            self._paused = False
            operation = await self.notify_orchestrator(ActionType.RESUME_AGENT)
        elif ActionType(message.request_type) == ActionType.DELETE_AGENT:
            self._paused = True
            self._policies = None
            self._public_information = None
            self._private_information = None
            operation = await self.notify_orchestrator(ActionType.DELETE_AGENT)
            self._user = None
            print("DELETED!")
            print(f"Name: {self._user}, Pub: {self._policies}, Priv: {self._public_information}, Policy: {self._private_information}")

        return operation

    @message_handler
    async def change_user_information(self, message : UserInformation, context : MessageContext) -> Status:
        self._policies = message.policies
        self._private_information = message.private_information
        self._public_information = message.public_information

        return Status.COMPLETED