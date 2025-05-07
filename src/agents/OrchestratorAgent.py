import asyncio
import json
from asyncio import Task
from typing import Dict, List, Optional, Tuple, Set, Any, Coroutine
from autogen_core import (AgentId, MessageContext, RoutedAgent, SingleThreadedAgentRuntime,
                          message_handler, type_subscription, TopicId, DefaultTopicId)
from autogen_core.model_context import BufferedChatCompletionContext
from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage

from src.enums import Status
from src.database import log_event
from src.models import (ConfigurationMessage, PairingRequest, PairingResponse, GetRequest,
                        GetResponse, UserInformation, ActionRequest, FeedbackMessage)
from src.enums import (json_pair, AgentRelations, AgentRelation_full, relation_triplet,
                       str_pair, RequestType, Relation, ActionType)

@type_subscription(topic_type="orchestrator_agent")
class OrchestratorAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient, model_client_name : str):
        super().__init__("orchestrator_agent")
        print(f"Created an Orchestrator: '{self.id}'")

        self._model_client = model_client
        self._model_client_name = model_client_name
        self._registered_agents: Set[str] = set()
        self._paused_agents: Set[str] = set()
        self._agent_information: Dict[str, json_pair] = {}
        self._matched_agents: AgentRelation_full = {}
        self._model_context_dict : Dict[str_pair, BufferedChatCompletionContext] = {}
        self._agents_lock = asyncio.Lock()

    async def get_public_information(self, requested_user : str) -> str:
        public_information : dict = {}
        async with self._agents_lock:
            public_information = self._agent_information.get(requested_user)[0]

        print(public_information)

        return '\n'.join([item['content'] for item in public_information])

    async def pause_agent(self, agent_id : str) -> None:
        async with self._agents_lock:
            if agent_id in self._paused_agents or agent_id not in self._registered_agents:
                return

            self._registered_agents.remove(agent_id)
            self._paused_agents.add(agent_id)

        print("PAUSED: ", agent_id)

    async def resume_agent(self, agent_id : str) -> None:
        async with self._agents_lock:
            if agent_id not in self._paused_agents or agent_id in self._registered_agents:
                return

            self._paused_agents.remove(agent_id)
            self._registered_agents.add(agent_id)

        print("RESUME: ", agent_id)

    async def delete_agent(self, agent_id : str) -> None:
        async with self._agents_lock:
            if agent_id in self._paused_agents:
                self._paused_agents.remove(agent_id)
            if agent_id in self._registered_agents:
                self._registered_agents.remove(agent_id)

        print("DELETE: ", agent_id)

    async def reset_agent_pairings(self, agent_id : str) -> None:
        print(f"Resetting {agent_id} pairings...")
        async with self._agents_lock:
            print(f"Previous matches {self._matched_agents} and registered {self._registered_agents}")
            if not (agent_id in self._registered_agents or agent_id in self._paused_agents):
                return

        agents_relation_full = await self.get_matched_agents(full=True)

        keys_to_remove = []
        for key in agents_relation_full:
            if agent_id in key[0] or agent_id in key[1]:
                keys_to_remove.append(key)

        print(f"Keys to remove: {keys_to_remove}")

        async with self._agents_lock:
            for key_pair in keys_to_remove:
                del self._matched_agents[key_pair]

            print(f"Updated connections: {self._matched_agents}")

    async def get_registered_agents(self) -> set[str]:
        async with self._agents_lock:
            return self._registered_agents.copy()

    async def get_matched_agents(self, full : bool = False) -> AgentRelations | AgentRelation_full:
        async with self._agents_lock:
            agent_made_matches = self._matched_agents.copy()

        if full:
            return agent_made_matches

        matches : AgentRelations = {}

        for key, value in agent_made_matches.items():
            matches[key] = value[self._model_client_name][0]

        return matches

    async def get_matches_for_agent(self, agent_id: str) -> AgentRelations:
        matches_copy = await self.get_matched_agents()

        matches_for_agent : AgentRelations = {}

        for agent_pair, relation in matches_copy.items():
            if agent_id in agent_pair:
                matches_for_agent[agent_pair] = relation

        return matches_for_agent

    async def get_human_pending_requests(self, agent_id : str):
        matches_copy = await self.get_matched_agents()

        print(f"Current: {self._matched_agents}")

        pending_requests : Dict[str, str] = {}

        for agent_pair, relation in matches_copy.items():
            if agent_id == agent_pair[0] and matches_copy[agent_pair] == Relation.ACCEPTED:
                if matches_copy[(agent_pair[1], agent_pair[0])] == Relation.ACCEPTED:
                    async with self._agents_lock:
                        if self._matched_agents[agent_pair][self._model_client_name][1] != Relation.UNCONTACTED:
                            continue

                    pending_requests[agent_pair[1]] = await self.get_public_information(agent_pair[1])

        print(f"Returning: {pending_requests}")

        return pending_requests

    async def get_established_relations(self, agent_id : str):
        matches = await self.get_matched_agents(full=True)

        print(f"Extracted {matches}")

        pending_requests: Dict[str, str] = {}

        for agent_pair, relation_triplet in matches.items():
            relation_triplet = relation_triplet[self._model_client_name]
            if agent_id == agent_pair[0] and relation_triplet[1] == Relation.USER_ACCEPTED:
                if matches[(agent_pair[1], agent_pair[0])][self._model_client_name][1] == Relation.USER_ACCEPTED:
                    pending_requests[agent_pair[1]] = await self.get_public_information(agent_pair[1])

        print(f"ReturningE: {pending_requests}")

        return pending_requests

    async def get_unfeedback_relations(self, agent_id : str):
        matches = await self.get_matched_agents()

        pending_requests: Dict[str, str] = {}

        for agent_pair, relation_triplet in matches.items():
            if agent_id == agent_pair[0] and relation_triplet in [Relation.ACCEPTED, Relation.REFUSED]:
                if matches[(agent_pair[1], agent_pair[0])] == Relation.UNCONTACTED:
                    pending_requests[agent_pair[1]] = await self.get_public_information(agent_pair[1])

        print(f"ReturningU: {pending_requests}")

        return pending_requests

    async def get_agent_decision(self, sender : str, receiver : str) -> Relation:
        async with self._agents_lock:
            return self._matched_agents[sender, receiver][self._model_client_name][0]

    async def get_human_decision(self, sender : str, receiver : str) -> Relation:
        async with self._agents_lock:
            return self._matched_agents[sender, receiver][self._model_client_name][1]

    async def get_user_rules(self, sender: str, receiver: str) -> list:
        async with self._agents_lock:
            return self._matched_agents[sender, receiver][self._model_client_name][2]

    async def check_response(self, sender : str, receiver : str, sender_information : str, receiver_policies : str, reasoning : str) -> str:
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

        async with self._agents_lock:
            sender_information = self._agent_information[sender]
            receiver_information = self._agent_information[receiver]

        receiver_policies = json.dumps(receiver_information[1], indent=4, sort_keys=True)
        sender_public_information = json.dumps(sender_information[0], indent=4, sort_keys=True)

        self._model_context_dict[(sender, receiver)] = BufferedChatCompletionContext(buffer_size=5)

        pair_response: PairingResponse = await self.send_message(
            PairingRequest(
                requester=sender, requester_information=sender_public_information,
                feedback=feedback, receiver=receiver
            ),
            AgentId("my_agent", receiver)
        )
        await self._model_context_dict[(sender, receiver)].add_message(UserMessage(content=pair_response.reasoning, source=sender))

        # To Do: determine if the orchestrator should check the model answers.
        check_pairing = 'VALID'

        '''check_pairing = await self.check_response(
            sender, receiver, sender_public_information,
            receiver_policies, pair_response.reasoning
        )'''

        await log_event(
            event_type="pairing_request",
            source=sender,
            data=PairingRequest(
                requester=sender,
                requester_information=sender_public_information,
                feedback=feedback,
                receiver=receiver
            )
        )

        await log_event(
            event_type="pairing_decision",
            source=receiver,
            data={
                "requester": sender,
                "receiver" : receiver,
                "decision": pair_response.answer,
                "reasoning": pair_response.reasoning[:500]
            }
        )

        if 'INVALID' in check_pairing.splitlines()[0]:
            feedback = f"Previous agent Reasoning: {pair_response.reasoning}\nFEEDBACK: {check_pairing.splitlines()[1:]}"
        elif 'VALID' in check_pairing.splitlines()[0]:
            async with self._agents_lock:
                for key, value in pair_response.answer.items():
                    self._matched_agents[(sender, receiver)][key] = (value, Relation.UNCONTACTED, [])
            return
        else:
            print(f"ERROR: Unknown answer when handling pairing request to {receiver} from {sender}...")
            return

        async with self._agents_lock:
            for key, value in pair_response.answer.items():
                self._matched_agents[(sender, receiver)][key] = (value, Relation.UNCONTACTED, [])

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

        print(f"PAIRINGS TERMINATED: {await self.get_matched_agents(full=True)}")

    @message_handler
    async def agent_configuration(self, message: ConfigurationMessage, context: MessageContext) -> None:
        async with self._agents_lock:
            registered = (message.user in self._registered_agents or message.user in self._paused_agents)

        if not registered and message.user == context.sender.key:
            for agent in self._registered_agents:
                if self._matched_agents.get((agent, message.user)) is None:
                    self._matched_agents[(agent, message.user)] : Dict[str, relation_triplet] = {}
                    self._matched_agents[(agent, message.user)] = {self._model_client_name: (Relation.UNCONTACTED, Relation.UNCONTACTED, [])}
                    self._matched_agents[(message.user, agent)] = {self._model_client_name: (Relation.UNCONTACTED, Relation.UNCONTACTED, [])}

            self._registered_agents.add(message.user)
            self._agent_information[message.user] = (message.user_information, message.user_policies)

            # in a more complex application maybe this could be scheduled as a background task: `asyncio.create_task`
            await self.match_agents(message.user)
            #return asyncio.create_task(self.match_agents(message.user))

        await log_event(
            event_type="agent_configuration",
            source=message.user,
            data={
                "public_information" : message.user_information,
                "policies" : message.user_policies
            }
        )

    @message_handler
    async def get_request(self, message: GetRequest, context: MessageContext) -> GetResponse:
        answer = GetResponse(request_type=message.request_type)
        if RequestType(message.request_type) == RequestType.GET_AGENT_RELATIONS:
            answer.agents_relation = await self.get_matched_agents()
        elif RequestType(message.request_type) == RequestType.GET_AGENT_RELATIONS_FULL:
            answer.agents_relation_full = await self.get_matched_agents(full=True)
        elif RequestType(message.request_type) == RequestType.GET_REGISTERED_AGENTS:
            answer.registered_agents= await self.get_registered_agents()
        elif RequestType(message.request_type) == RequestType.GET_PERSONAL_RELATIONS:
            answer.agents_relation= await self.get_matches_for_agent(message.user)
        elif RequestType(message.request_type) == RequestType.GET_PENDING_HUMAN_APPROVAL:
            answer.users_and_public_info = await self.get_human_pending_requests(message.user)
        elif RequestType(message.request_type) == RequestType.GET_ESTABLISHED_RELATIONS:
            answer.users_and_public_info = await self.get_established_relations(message.user)
        elif RequestType(message.request_type) == RequestType.GET_UNFEEDBACK_RELATIONS:
            answer.users_and_public_info = await self.get_unfeedback_relations(message.user)

        return answer

    @message_handler
    async def action_request(self, message : ActionRequest, context: MessageContext) -> None:
        if ActionType(message.request_type) == ActionType.PAUSE_AGENT:
            await self.pause_agent(message.user)
        elif ActionType(message.request_type) == ActionType.RESUME_AGENT:
            await self.resume_agent(message.user)
        elif ActionType(message.request_type) == ActionType.DELETE_AGENT:
            await self.reset_agent_pairings(message.user)
            await self.delete_agent(message.user)
        elif ActionType(message.request_type) == ActionType.RESET_AGENT:
            await self.reset_agent_pairings(message.user)
            await self.delete_agent(message.user)

        await log_event(
            event_type="agent_status_change",
            source=message.user,
            data=ActionRequest(
                request_type=message.request_type,
            )
        )

    @message_handler
    async def human_in_the_loop(self, message: FeedbackMessage, context: MessageContext) -> Status:
        print("FEEDBACK RECEIVED!")
        async with self._agents_lock:
            key = (message.sender, message.receiver)
            if key not in self._matched_agents:
                print(f"No matching record found for {message.sender}->{message.receiver}")
                return Status.FAILED

            models_dict = self._matched_agents[key]
            if not models_dict:
                print("No models present to update.")
                return Status.FAILED

            for model_name, (orig_decision, _old_feedback, orig_policies) in list(models_dict.items()):
                models_dict[model_name] = (
                    orig_decision,
                    Relation(message.feedback),
                    orig_policies
                )

        await log_event(
            event_type="human_feedback",
            source=message.sender,
            data=message
        )
        return Status.COMPLETED
