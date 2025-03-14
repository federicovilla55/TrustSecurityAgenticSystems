from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set, Any, Coroutine
from autogen_core import AgentId, MessageContext, RoutedAgent, SingleThreadedAgentRuntime, message_handler, type_subscription, TopicId, DefaultTopicId
from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient

from ..enums import *
from ..models import (
    SetupMessage, ConfigurationMessage, PairingRequest,
    PairingResponse, GetRequest, MatchedAgents
)
from ..utils import extract_section, remove_chain_of_thought, separate_categories

class MyAgent(RoutedAgent):
    def __init__(self, description : str, model_client: ChatCompletionClient):
        super().__init__(description)
        self._private_information = None
        self._policies = None
        self._public_information = None
        print(f"You just created an Agent: '{self.id}'")

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

    async def evaluate_connection(self, context, prompt, user_information_prompt) -> PairingResponse:
        llm_answer = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt, source=self._user),
                      UserMessage(content=user_information_prompt, source=self._user), ],
            cancellation_token=context.cancellation_token,
        )

        print(f"{'*' * 20}\nPROMPT REQUEST: {[self._system_message, UserMessage(content=prompt, source=self._user), UserMessage(content=user_information_prompt, source=self._user)]}\n{'*' * 20}\n")
        print(f"{'-' * 20}\n{self.id} ANSWER: {llm_answer.content}\n{'-' * 20}\n")

        result = remove_chain_of_thought(llm_answer.content)

        if 'REJECT' in result.splitlines()[0].upper():
            return PairingResponse(Relation.REFUSED, result.splitlines()[1:])
        elif 'ACCEPT' in result.splitlines()[0].upper():
            return PairingResponse(Relation.ACCEPTED, result.splitlines()[1:])
        else:
            print(f"ERROR: Unknown answer when handling pairing request...")
            return PairingResponse(Relation.REFUSED, result)

    @message_handler
    async def handle_setup(self, message: SetupMessage, context: MessageContext) -> None:
        self._user = message.user
        print(f"'{self.id}' Received setup message {message}")

        prompt_information = f"""
                    Extract ALL user policies from {self.id} message, following these rules:
                    - Answer with a list of policies provided by the user.
                    - Identify both explicit and implicit policies.
                    - Capture all content provided by the user.
                    - Separate rules with multiple conditions into individual items.
                    - Convert positive constraints to negative statements.
                    - Respect user privacy and do not share information the user explicitly wants to be kept private.
                    - Rules may exclude each other. Understand the rules logic and divide or aggregate them.
                    - Add precise context to each rule to reduce uncertainty.
                    EXTRACT ALL public personal information from {self.id} message, following these rules:
                    - Include Organizations, Jobs and Interests explicitly mentioned.
                    - Capture all content provided by the user.
                    - Exclude information the user explicitly wanted to be kept private.
                    - Answer with a list of information provided by the user.
                    - Add precise context to each information to reduce uncertainty.
                    EXTRACT ALL private information from {self.id} message, following these rules:
                    - Include all information the user explicitly wanted to be kept private. 
                    - Exclude public personal information.
                    - Answer with a list of information provided by the user.
                    - Add precise context to each information to reduce uncertainty.
                    
                    When answering, categorize your response into three sections using the following format:
                    **Public Information**:
                    - [List {self.id} public information]
                    **Private Information**:
                    - [List {self.id} private information]
                    **Policies**:
                    - [List {self.id} policies]
                    Separate each section with "---" and avoid mixing categories.

                    This is {self.id} message: {message.content}.
                    """

        llm_answer = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt_information, source=self._user)],
            cancellation_token=context.cancellation_token,
        )

        result = remove_chain_of_thought(llm_answer.content)
        print(f"RAW: {result}.")
        self._policies, self._public_information, self._private_information = separate_categories(result)

        print(f"{'='*20}\n{self._user} POLICIES: {self._policies}")
        print(f"{self._user} PUBLIC INFORMATION: {self._public_information}\n")
        print(f"{self._user} PRIVATE INFORMATION: {self._private_information}\n{'=' * 20}\n")

        configuration_message = ConfigurationMessage(
            user=self._user,
            user_policies=self._policies,
            user_information=self._public_information,
        )

        await self.publish_message(
            configuration_message, topic_id=TopicId("orchestrator_agent", "default")
        )

    @message_handler
    async def handle_pairing_request(self, message: PairingRequest, context: MessageContext) -> PairingResponse:
        #print(f"'{self.id}' Received pairing request from '{message.user}'")
        prompt = f"""Evaluate the connection request from {message.requester} to {self.id} and accept or reject it.
                     You can accept a connection if the {message.requester}'s information adhere to the:
                     - {self.id} defined policies;
                     - default policies;
                     Find if there is compatibility between the {message.requester}'s information and {self.id}'s policies and information.
                     These are {message.requester}'s public information: {message.requester_information}.\n
                     Respond with ONLY "ACCEPT" or "REJECT" in the first line of your response.
                     Provide a reasoning for each policy if it was satisfied or not.
                     Only respond based on the provided policies and information. Do not make broader considerations.
                    """

        if message.feedback != "":
            prompt += f"\nConsider this feedback on a previous answer: {message.feedback}."

        user_information_prompt = f"These are {self.id}'s policies: {self._policies}.\nThese are {self.id}\npublic information: {self._public_information}.\nThese are {self.id} private information: {self._private_information}."
        # UserMessage(content=prompt, source=self._user),

        return await self.evaluate_connection(context, prompt, user_information_prompt)