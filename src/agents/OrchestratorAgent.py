import asyncio
from typing import Dict, List, Optional, Tuple, Set, Any, Coroutine
from autogen_core import AgentId, MessageContext, RoutedAgent, SingleThreadedAgentRuntime, message_handler, type_subscription, TopicId, DefaultTopicId
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
        self._agent_information: Dict[str, str_pair] = {}
        self._matched_agents: AgentRelations = {}

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
                - Your evalutation should not move away from the provided information.
                - INVALID only if there are severe policy violations. 
                - Policies and information cannot be further explained, corrected or modified.
                - Respond in the first line of your response with ONLY "VALID" if {receiver}'s reasoning is correct, with "INVALID" if some policy evaluation is wrong. 
                - Provide a feedback in case the reasoning is invalid.
                
                These are {sender}'s public information: {sender_information}.
                
                These are {receiver}'s policies: {receiver_policies}.   
                
                This is {receiver}'s reasoning: {reasoning}.             
                """

        llm_answer = await self._model_client.create(
            messages=[UserMessage(content=prompt, source="OrchestratorAgent"),],
        )

        return llm_answer.content


    async def match_agents(self, user_to_add: str) -> None:
        print(f"Matching agents with {user_to_add}...")

        registered_agents_copy = await self.get_registered_agents()
        matched_agents_copy = await self.get_matched_agents()
        async with self._agents_lock:
            agent_information_copy = self._agent_information.copy()

        for agent in registered_agents_copy:
            if agent != user_to_add:
                if matched_agents_copy.get((agent, user_to_add)) == Relation.UNCONTACTED and matched_agents_copy.get(
                        (user_to_add, agent)) == Relation.UNCONTACTED:
                    print(f"Contacting: {agent}...")

                    feedback = ""
                    while True:
                        response_1 : PairingResponse = await self.send_message(
                            PairingRequest(requester=user_to_add,
                                           requester_information=agent_information_copy[user_to_add][0], feedback=feedback),
                            AgentId("my_agent", agent)
                        )
                        check_1 = await self.check_response(user_to_add, agent, agent_information_copy[user_to_add][0], agent_information_copy[agent][1], response_1.reasoning)
                        if 'INVALID' in check_1.splitlines()[0]:
                            print(f"INVALID. Now I should give a feedback to {agent} for connection with {user_to_add}: {check_1}.\n")
                            feedback = f"Reasoning: {response_1.reasoning}\nFEEDBACK: {check_1.splitlines()[1:]}"
                        elif 'VALID' in check_1.splitlines()[0]:
                            print(f"VALID. {agent} for connection from {user_to_add}\n")
                            matched_agents_copy[(agent, user_to_add)] = response_1.answer
                            break
                        else:
                            print(f"ERROR: Unknown answer when handling pairing request to {agent} from {user_to_add}...")
                            break
                    feedback = ""
                    while True:
                        response_2 : PairingResponse = await self.send_message(
                            PairingRequest(requester=agent,
                                           requester_information=agent_information_copy[agent][0], feedback=feedback),
                            AgentId("my_agent", user_to_add)
                        )
                        check_2 = await self.check_response(agent, user_to_add, agent_information_copy[agent][0], agent_information_copy[user_to_add][1], response_2.reasoning)
                        if 'INVALID' in check_2.splitlines()[0]:
                            print(f"INVALID. Now I should give a feedback to {user_to_add} for connection with {agent}: {check_2}.\n")
                            feedback = f"Reasoning: {response_2.reasoning}\nFEEDBACK: {check_2.splitlines()[1:]}"
                        elif 'VALID' in check_2.splitlines()[0]:
                            print(f"VALID. {user_to_add} for connection from {agent}\n")
                            matched_agents_copy[(user_to_add, agent)] = response_2.answer
                            break
                        else:
                            print(f"ERROR: Unknown answer when handling pairing request to {user_to_add} from {agent}...")
                            break


        async with self._agents_lock:
            for agent in registered_agents_copy:
                if agent != user_to_add:
                    print(f"UPDATING: agent: {agent} - {user_to_add}...")
                    self._matched_agents[(agent, user_to_add)] = matched_agents_copy[(agent, user_to_add)]
                    self._matched_agents[(user_to_add, agent)] = matched_agents_copy[(user_to_add, agent)]


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
