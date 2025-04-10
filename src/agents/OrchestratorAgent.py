import asyncio
import json
from asyncio import Task
from typing import Dict, List, Optional, Tuple, Set, Any, Coroutine
from autogen_core import AgentId, MessageContext, RoutedAgent, SingleThreadedAgentRuntime, message_handler, type_subscription, TopicId, DefaultTopicId
from autogen_core.model_context import BufferedChatCompletionContext
from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage

from .. import PairingResponse
from ..enums import *
from ..models import (
    ConfigurationMessage, PairingRequest, GetRequest, GetResponse
)

@type_subscription(topic_type="orchestrator_agent")
class OrchestratorAgent(RoutedAgent):
    def __init__(self, description : str, model_client: ChatCompletionClient):
        super().__init__(description)
        print(f"Created an Orchestrator: '{self.id}'")

        self._model_client = model_client
        self._registered_agents: Set[str] = set()
        self._paused_agents: Set[str] = set()
        self._agent_information: Dict[str, json_pair] = {}
        self._matched_agents: AgentRelations = {}
        self._model_context_dict : Dict[str_pair, BufferedChatCompletionContext] = {}
        self._agents_lock = asyncio.Lock()

    async def pause_agent(self, agent_id : str) -> None:
        async with self._agents_lock:
            if agent_id in self._paused_agents or agent_id not in self._registered_agents:
                return

            self._registered_agents.remove(agent_id)
            self._paused_agents.add(agent_id)

    async def resume_agent(self, agent_id : str) -> None:
        async with self._agents_lock:
            if agent_id not in self._paused_agents or agent_id in self._registered_agents:
                return

            self._paused_agents.remove(agent_id)
            self._registered_agents.add(agent_id)

    async def delete_agent(self, agent_id : str) -> None:
        async with self._agents_lock:
            if agent_id in self._paused_agents:
                self._paused_agents.remove(agent_id)
            if agent_id in self._registered_agents:
                self._registered_agents.remove(agent_id)

    async def get_registered_agents(self) -> set[str]:
        async with self._agents_lock:
            return self._registered_agents.copy()

    async def get_matched_agents(self) -> AgentRelations:
        async with self._agents_lock:
            return self._matched_agents.copy()

    async def get_matches_for_agent(self, agent_id: str) -> AgentRelations:
        matches_copy = await self.get_matched_agents()

        matches_for_agent : AgentRelations = {}

        for agent_pair, relation in matches_copy.items():
            if agent_id in agent_pair:
                matches_for_agent[agent_pair] = relation

        return matches_for_agent

    async def check_response(self, sender : str, receiver : str, sender_information : str, receiver_policies : str, reasoning : str) -> str:
        return "VALID"

        prompt = f"""
                You are the Policy Enforcement Orchestrator. Your job is to evaluate the reasoning {receiver} made on the policies.
                The received reasoning includes a series of policies ID and a status regarding whether the policy was UNUSED, used with private information or
                if it was used to decide whether the connection should be accepted ('POSITIVE') or rejected ('NEGATIVE'). 
                You have to analyze the policies that lead to accepting or rejecting the connection and for each policy determine if it was applied correctly. 
                - Your evaluation should not move away from the provided information.
                - Policies and information cannot be further explained, corrected or modified.
                - Respond in the first line of your response with ONLY "VALID" if {receiver}'s reasoning is correct, with "INVALID" if some policy evaluation are wrong. 
                - Provide a feedback in case the reasoning is invalid with a list of policies that should be considered differently and why.
                
                These are {sender}'s public information: {sender_information}.
                
                These are {receiver}'s policies: {receiver_policies}.   
                
                This is {receiver}'s reasoning: {reasoning}.             
                """

        llm_answer = await self._model_client.create(
            messages=[UserMessage(content=prompt, source="OrchestratorAgent")] + (await self._model_context_dict[(sender, receiver)].get_messages()),
        )

        await self._model_context_dict[(sender, receiver)].add_message(UserMessage(content=llm_answer.content, source="OrchestratorAgent"))

        return llm_answer.content

    async def pair_agent_with_feedback(self, sender : str, receiver : str) -> None:
        # The sender sends its public information while the receiver checks this information using its policies and private information
        feedback = ""

        print("CHECKING...")

        async with self._agents_lock:
            sender_information = self._agent_information[sender]
            receiver_information = self._agent_information[receiver]

        receiver_policies = json.dumps(receiver_information[1], indent=4, sort_keys=True)
        sender_public_information = json.dumps(sender_information[0], indent=4, sort_keys=True)

        pair_response: PairingResponse = PairingResponse(Relation.UNCONTACTED, "")

        self._model_context_dict[(sender, receiver)] = BufferedChatCompletionContext(buffer_size=5)
        for i in range(5):
            pair_response: PairingResponse = await self.send_message(
                PairingRequest(
                    requester=sender, requester_information=sender_public_information,
                    feedback=feedback
                ),
                AgentId("my_agent", receiver)
            )
            await self._model_context_dict[(sender, receiver)].add_message(UserMessage(content=pair_response.reasoning, source=sender))
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

        async with self._agents_lock:
            self._matched_agents[(sender, receiver)] = pair_response.answer

    async def match_agents(self, user_to_add: str) -> None:
        registered_agents_copy = await self.get_registered_agents()
        registered_agents_copy.remove(user_to_add)

        matched_agents_copy = await self.get_matched_agents()

        for registered_agent in registered_agents_copy:
            # Does the already registered agents accept the pair with the new agent?
            if matched_agents_copy.get((user_to_add, registered_agent)) == Relation.UNCONTACTED:
                await self.pair_agent_with_feedback(user_to_add, registered_agent)

            # Does the new agent accept the pair with the already registered agent?
            if matched_agents_copy.get((registered_agent, user_to_add)) == Relation.UNCONTACTED:
                await self.pair_agent_with_feedback(registered_agent, user_to_add)

    @message_handler
    async def agent_configuration(self, message: ConfigurationMessage, context: MessageContext) -> None:
        print("HEY CONFIG")
        async with self._agents_lock:
            registered = (message.user in self._registered_agents or message.user in self._paused_agents)

        if not registered and message.user == context.sender.key:
            for agent in self._registered_agents:
                if self._matched_agents.get((agent, message.user)) is None:
                    self._matched_agents[(agent, message.user)] = Relation.UNCONTACTED
                    self._matched_agents[(message.user, agent)] = Relation.UNCONTACTED

            self._registered_agents.add(message.user)
            self._agent_information[message.user] = (message.user_information, message.user_policies)

            # in a more complex application maybe this could be scheduled as a background task: `asyncio.create_task`
            await self.match_agents(message.user)
            #return asyncio.create_task(self.match_agents(message.user))

    @message_handler
    async def get_request(self, message: GetRequest, context: MessageContext) -> GetResponse:
        answer = GetResponse(request_type=message.request_type)
        if RequestType(message.request_type) == RequestType.GET_AGENT_RELATIONS:
            answer.agents_relation= await self.get_matched_agents()
        elif RequestType(message.request_type) == RequestType.GET_REGISTERED_AGENTS:
            answer.registered_agents= await self.get_registered_agents()
        elif RequestType(message.request_type) == RequestType.GET_PERSONAL_RELATIONS:
            answer.agents_relation= await self.get_matches_for_agent(message.user)
        elif RequestType(message.request_type) == RequestType.PAUSE_AGENT:
            await self.pause_agent(message.user)
        elif RequestType(message.request_type) == RequestType.RESUME_AGENT:
            await self.resume_agent(message.user)
        elif RequestType(message.request_type) == RequestType.DELETE_AGENT:
            await self.delete_agent(message.user)

        return answer
