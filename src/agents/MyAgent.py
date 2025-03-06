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
from ..utils import extract_section, remove_chain_of_thought

class MyAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient):
        super().__init__("An helpful AI assistant")
        print(f"You just created an Agent: '{self.id}'")

        self._system_message = SystemMessage(
            content=f"""
            You are a Personal Policy Enforcement Agent for the user: {self.id}
            You act Exclusive to your user, for user's interest, privacy and security.
            You should be open to other agents that share same Organizations, Interests and Information. 
            Never act outside the default rules and the user configured rules.
            
            Your Core Functions:
            - Store and protect your user's private information and enforce defined policies.
            - Connect the user with other agents that follow the defined connection policies.
            - Evaluate ALL connection requests against User-defined rules (highest priority) and
              Default security policies (below)
            - Share ONLY information explicitly permitted by user policies.  
            
            Default Policies, may be overwritten by user policies.:  
            1. Mandatory Rejection Criteria  
               - Requester shares NO common interests or organizations.
               - Requester do not satisfy any rules.
            2. Information Sharing Limits
               - Never share specific information without explicit consent  
               - Do not share sensitive information such as precise locations, roles or projects  
               - Redact sensitive keywords (such as project names, internal codes)
            3. Connection Rules
               - Permit only connections in compliance with the user policies and requirements.
               - Enforce connections from users that share the same interests or from the same organization.
               - If multiple organizations are listed, a match on any one of the explicitly specified organizations. Other organizational affiliations should not affect the match decision
               - Presence of additional organizations or interest in the requester’s profile should not penalize the match.
               - For connection requests, only check for the explicitly mentioned organizations or interests
               - Follow strictly user policies and never override them.
               - Do not enforce too specific criteria when evaluating interests or organization
            """
        )

        self._model_client = model_client
        self.paired_agents : Set[str] = set()
        self.refused_agents : Set[str] = set()

    @message_handler
    async def handle_setup(self, message: SetupMessage, context: MessageContext) -> None:
        self._user = message.user
        print(f"'{self.id}' Received setup message {message}")

        prompt_policies = f"""POLICY EXTRACTION TASK: Extract ALL connection policies/rules from this user message following these rules:
                    - Answer with only the list of policies the user provided separated.
                    - Identify both explicit and implicit policies.
                    - Capture all content provided by the user.
                    - Separate a rules with multiple conditions into individual items.
                    - Convert negative statements to positive constraints.
                    - Some rules may exclude each other.
                    - Find rules that should be satisfied simultaneously and divide them.
                    - Recover precisely the logic in user rules (or, and, at least...)
                    - Ensure Completeness: Capture all relevant constraints provided by the user.
                    - Format as ONLY one rule per line in bullet points.
                    {self._user} Message: {message.content}.
                    """

        llm_answer = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt_policies, source=self._user)],
            cancellation_token=context.cancellation_token,
        )

        self._policies = remove_chain_of_thought(llm_answer.content)

        prompt_information = f"""INFORMATION EXTRACTION TASK: extract all personal information the user wants to share:
                    - Include Organizations, Jobs and Interests explicitly mentioned.
                    - Capture all content provided by the user.
                    - Exclude sensitive information such as precise locations, internal codes, or unapproved personal details.
                    - Include only user personal relevant information and not policies or matching information.
                    - Format as ONLY one information per line in bullet points.
                    - Add relevant context to each information
                    
                    {self._user} message: {message.content}.
                    {self._user} policies: {self._policies}.
                    """

        llm_answer = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt_information, source=self._user)],
            cancellation_token=context.cancellation_token,
        )

        self._information = remove_chain_of_thought(llm_answer.content)

        print(f"{'='*20}\n{self._user} POLICIES: {self._policies}")
        print(f"{self._user} INFORMATION: {self._information}\n{'='*20}\n")

        configuration_message = ConfigurationMessage(
            user=self._user,
            user_preferences=self._policies,
            user_information=self._information,
        )

        print(f"Configuration Message: {configuration_message}")

        await self.publish_message(
            configuration_message, topic_id=TopicId("orchestrator_agent", "default")
        )

    @message_handler
    async def handle_pairing_request(self, message: PairingRequest, context: MessageContext) -> PairingResponse:
        #print(f"'{self.id}' Received pairing request from '{message.user}'")

        prompt = f"""TASK: Evaluate the connection request from {message.user} and determine whether to accept or reject it.
                     You can accept a connection if the requester's information adhere some:
                     - default policies
                     - your user ({self.id}) defined policies: {self._policies} 
                     When checking policies deeply analyze them to find compatibility (expand names and add information and context).
                     These are (requester agent) {message.user}'s information: {message.user_information}.
                     Respond with ONLY "ACCEPT" or "REJECT."
                     Provide a brief explanation for logging purposes.
                    """

        user_information_prompt = f"These are your agent ({self.id}) information: {self._information}"
        user_policies_prompt = f"These are your agent ({self.id}) policies: {self._policies}"

        llm_answer = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=user_information_prompt, source=self._user),
                      UserMessage(content=prompt, source=self._user), UserMessage(content=user_policies_prompt, source=self._user)],
            cancellation_token=context.cancellation_token,
        )



        print(f"{'*'*20}\nPROMPT REQUEST: {[self._system_message, UserMessage(content=prompt, source=self._user)]}\n{'*'*20}\n")
        print(f"{'-'*20}\n{self.id} Answer to {message.user}: {llm_answer.content}\n{'-'*20}\n")

        if 'REJECT' in remove_chain_of_thought(llm_answer.content).upper():
            return PairingResponse(Relation.REFUSED)
        elif 'ACCEPT' in remove_chain_of_thought(llm_answer.content).upper():
            return PairingResponse(Relation.ACCEPTED)
        else:
            print(f"ERROR: Unknown answer when handling pairing request...")
            return PairingResponse(Relation.REFUSED)