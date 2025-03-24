import asyncio
import json
from typing import Dict, List, Optional, Tuple, Set, Any, Coroutine
from autogen_core import AgentId, MessageContext, RoutedAgent, SingleThreadedAgentRuntime, message_handler, type_subscription, TopicId, DefaultTopicId
from autogen_core.model_context import BufferedChatCompletionContext
from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage

from .. import PairingResponse
from ..enums import *
from ..models import (
    ConfigurationMessage, PairingRequest, GetRequest, MatchedAgents
)

@type_subscription(topic_type="orchestrator_agent")
class OrchestratorAgent(RoutedAgent):
    def __init__(self, description : str, model_client: ChatCompletionClient):
        super().__init__(description)
        print(f"Created an Orchestrator: '{self.id}'")

        self._model_client = model_client
        self._registered_agents: Set[str] = set()
        self._agent_information: Dict[str, json_pair] = {}
        self._matched_agents: AgentRelations = {}
        self._model_context_dict : Dict[str_pair, BufferedChatCompletionContext] = {}
        self._agents_lock = asyncio.Lock()

    async def get_registered_agents(self) -> set[str]:
        async with self._agents_lock:
            return self._registered_agents.copy()

    async def get_matched_agents(self) -> AgentRelations:
        async with self._agents_lock:
            return self._matched_agents.copy()

    async def check_response(self, sender : str, receiver : str, sender_information : str, receiver_policies : str, reasoning : str) -> str:
        prompt = f"""
                You are the Policy Enforcement Orchestrator. 
                Your job is to evaluate the reasoning {receiver} made.
                - Your evaluation should not be too strictly.
                - Your evaluation should not move away from the provided information.
                - INVALID only if there are severe policy violations. 
                - Policies and information cannot be further explained, corrected or modified.
                - Respond in the first line of your response with ONLY "VALID" if {receiver}'s reasoning is correct, with "INVALID" if some policy evaluation is wrong. 
                - Provide a feedback in case the reasoning is invalid.
                
                These are {sender}'s public information: {sender_information}.
                
                These are {receiver}'s policies: {receiver_policies}.   
                
                This is {receiver}'s reasoning: {reasoning}.             
                """

        llm_answer = await self._model_client.create(
            messages=[UserMessage(content=prompt, source="OrchestratorAgent")] + await self._model_context_dict[(sender, receiver)].get_messages(),
        )

        await self._model_context_dict[(sender, receiver)].add_message(llm_answer)

        return llm_answer.content

    async def pair_agent_with_feedback(self, sender : str, receiver : str) -> None:
        # The sender sends its public information while the receiver checks this information using its policies and private information
        feedback = ""

        async with self._agents_lock:
            sender_information = self._agent_information[sender]
            receiver_information = self._agent_information[receiver]

        receiver_policies = json.dumps(receiver_information[1], indent=4, sort_keys=True)
        sender_public_information = json.dumps(sender_information[0], indent=4, sort_keys=True)

        pair_response: PairingResponse = PairingResponse(Relation.UNCONTACTED, "")

        for i in range(5):
            self._model_context_dict[(sender, receiver)] = BufferedChatCompletionContext(buffer_size=5)
            pair_response: PairingResponse = await self.send_message(
                PairingRequest(
                    requester=sender, requester_information=sender_public_information,
                    feedback=feedback
                ),
                AgentId("my_agent", receiver)
            )
            await self._model_context_dict[(sender, receiver)].add_message(pair_response)
            check_pairing = await self.check_response(
                sender, receiver, sender_public_information,
                receiver_policies, pair_response.reasoning
            )
            if 'INVALID' in check_pairing.splitlines()[0]:
                feedback = f"Previous agent Reasoning: {pair_response.reasoning}\nFEEDBACK: {check_pairing.splitlines()[1:]}"
            elif 'VALID' in check_pairing.splitlines()[0]:
                async with self._agents_lock:
                    self._matched_agents[(sender, receiver)] = pair_response.answer
                return
            else:
                print(f"ERROR: Unknown answer when handling pairing request to {receiver} from {sender}...")
                break

        print("Exceeded Runtime.")

        async with self._agents_lock:
            self._matched_agents[(sender, receiver)] = pair_response.answer

    async def match_agents(self, user_to_add: str) -> None:
        registered_agents_copy = await self.get_registered_agents()
        registered_agents_copy.remove(user_to_add)
        print("STARTED MATCHING.")

        matched_agents_copy = await self.get_matched_agents()

        for registered_agent in registered_agents_copy:
            # Does the already registered agents accept the pair with the new agent?
            if matched_agents_copy.get((user_to_add, registered_agent)) == Relation.UNCONTACTED:
                await self.pair_agent_with_feedback(user_to_add, registered_agent)

            # Does the new agent accept the pair with the already registered agent?
            if matched_agents_copy.get((registered_agent, user_to_add)) == Relation.UNCONTACTED:
                await self.pair_agent_with_feedback(registered_agent, user_to_add)

        print("ENDED MATCHING.")

    @message_handler
    async def agent_configuration(self, message: ConfigurationMessage, context: MessageContext) -> None:
        registered_agents_copy = await self.get_registered_agents()

        if message.user in registered_agents_copy or message.user == self.id or message.user != context.sender:
            async with self._agents_lock:
                for agent in registered_agents_copy:
                    if self._matched_agents.get((agent, message.user)) is None:
                        self._matched_agents[(agent, message.user)] = Relation.UNCONTACTED
                        self._matched_agents[(message.user, agent)] = Relation.UNCONTACTED

                self._registered_agents.add(message.user)
                self._agent_information[message.user] = (message.user_information, message.user_policies)

            # in a more complex application maybe this could be scheduled as a background task: `asyncio.create_task`
            await self.match_agents(message.user)

    @message_handler
    async def get_request(self, message: GetRequest, context: MessageContext) -> MatchedAgents:
        answer = MatchedAgents(request_type=message.request_type)
        if RequestType(message.request_type) == RequestType.GET_AGENT_RELATIONS:
            answer.agents_relation= await self.get_matched_agents()
        elif RequestType(message.request_type) == RequestType.GET_REGISTERED_AGENTS:
            answer.registered_agents= await self.get_registered_agents()

        return answer
