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
from src.enums import (json_pair, AgentRelations_PersonalAgents, CompleteAgentRelations,
                       str_pair, RequestType, Relation, ActionType, LLMRelations)

@type_subscription(topic_type="orchestrator_agent")
class OrchestratorAgent(RoutedAgent):
    """
    The OrchestratorAgent is a subclass of `RoutedAgent`, the base AutoGen class for the agents.
    This is the central agent of the multi-agent system: all the interactions between agents pass for the Orchestrator,
    which acts a middle-man between the agents, forwarding the messages from an agent to all the others.
    The central agent is responsible for managing the connections between agents and for the pairing process: when a new agent is created and
    its setup is completed, that agent contacts the orchestrator which forwards a pairing request from that agent to all the registered agents.
    The Orchestrator is responsible for saving all the agents registered in the platform, the users that paused their personal agent, the
    public information of each agent and the pairing status of each agent.
    The orchestrator saves the feedback each user sends for the agent-established connections.
    """
    def __init__(self, model_client: ChatCompletionClient, model_client_name : str):
        super().__init__("orchestrator_agent")
        print(f"Created an Orchestrator: '{self.id}'")

        self._model_client = model_client
        self._model_client_name = model_client_name
        self._registered_agents: Set[str] = set()
        self._paused_agents: Set[str] = set()
        self._agent_information: Dict[str, json_pair] = {}
        self._matched_agents: CompleteAgentRelations = {}
        self._model_context_dict : Dict[str_pair, BufferedChatCompletionContext] = {}
        self._agents_lock = asyncio.Lock()

    async def get_public_information(self, requested_user : str) -> str:
        """
        The method is called to get the public information of an agent given its ID, corresponding to the user's username.

        :param requested_user: A string containing the ID of the agent whose public information is requested.
        :return: A string containing the public information of the agent with the given ID. The information is converted from a JSON-like format to a string to be better used by the LLMs upon pairing evaluation.
        """
        public_information : dict = {}
        async with self._agents_lock:
            public_information = self._agent_information.get(requested_user)[0]

        print(public_information)

        return '\n'.join([item['content'] for item in public_information])

    async def pause_agent(self, agent_id : str) -> None:
        """
        The method is called to pause an agent given its ID.

        :param agent_id: A string containing the ID of the agent to pause.
        :return: None
        """
        async with self._agents_lock:
            if agent_id in self._paused_agents or agent_id not in self._registered_agents:
                return

            self._registered_agents.remove(agent_id)
            self._paused_agents.add(agent_id)

        print("PAUSED: ", agent_id)

    async def resume_agent(self, agent_id : str) -> None:
        """
        The method is called to resume an agent given its ID.

        :param agent_id: A string containing the ID of the agent to resume.
        :return: None
        """
        async with self._agents_lock:
            if agent_id not in self._paused_agents or agent_id in self._registered_agents:
                return

            self._paused_agents.remove(agent_id)
            self._registered_agents.add(agent_id)

        print("RESUME: ", agent_id)

    async def delete_agent(self, agent_id : str) -> None:
        """
        The method is called to delete an agent given its ID.

        :param agent_id: A string containing the ID of the agent to delete.
        :return: None
        """
        async with self._agents_lock:
            if agent_id in self._paused_agents:
                self._paused_agents.remove(agent_id)
            if agent_id in self._registered_agents:
                self._registered_agents.remove(agent_id)

        print("DELETE: ", agent_id)

    async def reset_agent_pairings(self, agent_id : str) -> None:
        """
        The method is called when an agent is reset and therefore the pairings that the agent had with other agents need to be deleted to ensure consistency
        between the orchestrator data structures.

        :param agent_id: A string containing the ID of the agent to reset.
        :return: None
        """
        print(f"Resetting {agent_id} pairings...")
        async with self._agents_lock:
            print(f"Previous matches {self._matched_agents} and registered {self._registered_agents}")
            if not (agent_id in self._registered_agents or agent_id in self._paused_agents):
                return

            del self._agent_information[agent_id]

        agents_relation_full : CompleteAgentRelations = await self.get_matched_agents_full()

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
        """
        The method is called to get the IDs of the agents registered and saved by the orchestrator.

        :return: A set of strings containing the IDs of the agents registered in the platform.
        """
        async with self._agents_lock:
            return self._registered_agents.copy()

    async def get_matched_personal_agents(self) -> AgentRelations_PersonalAgents:
        """
        The method is called to get the pairings of each agent as established by the personal agents' LLMs.
        The relations returned by this method are queried from the `_matched_agents` data structure, a dictionary of
        type `CompleteAgentRelations` that it is queried to return only the pairing information from the personal agent LLM's evaluations.

        :return: A dictionary that maps each agent pair to the corresponding personal agent LLM's decision.
        """
        async with self._agents_lock:
            agent_made_matches = self._matched_agents.copy()

        matches : AgentRelations_PersonalAgents = {}

        for key, value in agent_made_matches.items():
            matches[key] = value[0][self._model_client_name][0]

        return matches

    async def get_matched_agents_full(self) -> CompleteAgentRelations:
        """
        The method is called to get the full information from the connections made by the personal agents and the feedback the users provided.
        The method returns a copy of the data structure with the requested information.

        :return: A structure of type `CompleteAgentRelations` containing a copy of the information saved by the orchestrator.
        """
        async with self._agents_lock:
            return self._matched_agents.copy()


    async def get_matches_for_agent(self, agent_id: str) -> AgentRelations_PersonalAgents:
        """
        The method returns a data structure containing the pairing the agent with the provided ID made.

        :param agent_id: A string containing the ID of the agent.
        :return: A dictionary that maps for each couple of user IDs the personal agent's LLM decision.
        """
        matches_copy : AgentRelations_PersonalAgents = await self.get_matched_personal_agents()

        matches_for_agent : AgentRelations_PersonalAgents = {}

        for agent_pair, relation in matches_copy.items():
            if agent_id in agent_pair:
                matches_for_agent[agent_pair] = relation

        return matches_for_agent

    async def get_human_pending_requests(self, agent_id : str) -> Dict[str, str]:
        """
        The method returns, given an `agent_id`, the agent IDs and public information of the connections accepted by both personal agents but still left to be evaluated by the user.
        The user should mark the connections returned by this method as correct or wrong.

        :param agent_id: A string containing the ID of the agent whose pairings are requested.
        :return: A dictionary that maps each agent ID to its corresponding public information.
        """
        matches_copy : AgentRelations_PersonalAgents = await self.get_matched_personal_agents()

        print(f"Current: {self._matched_agents}")

        pending_requests : Dict[str, str] = {}

        for agent_pair, relation in matches_copy.items():
            if agent_id == agent_pair[0] and matches_copy[agent_pair] == Relation.ACCEPTED:
                if matches_copy[(agent_pair[1], agent_pair[0])] == Relation.ACCEPTED:
                    async with self._agents_lock:
                        if self._matched_agents[agent_pair][1] != Relation.UNCONTACTED:
                            continue

                    pending_requests[agent_pair[1]] = await self.get_public_information(agent_pair[1])

        print(f"Returning: {pending_requests}")

        return pending_requests

    async def get_established_relations(self, agent_id : str) -> Dict[str, str]:
        """
        The method returns, given an `agent_id`, a dictionary containing the IDs and corresponding public information of the user-established connections (connections both users accepted).
        The method returns a subset of all the relationships both the users manually accepted (by providing feedback).

        :param agent_id: A string containing the user ID whose established pairing is requested.
        :return: A dictionary that maps each agent ID the user established a connection to the public information of that agent.
        """
        matches : CompleteAgentRelations = await self.get_matched_agents_full()

        print(f"Extracted {matches}")

        pending_requests: Dict[str, str] = {}

        for agent_pair, complete_relation in matches.items():
            if agent_id == agent_pair[0] and complete_relation[1] == Relation.USER_ACCEPTED:
                if matches[(agent_pair[1], agent_pair[0])][1] == Relation.USER_ACCEPTED:
                    pending_requests[agent_pair[1]] = await self.get_public_information(agent_pair[1])

        return pending_requests

    async def get_unfeedback_relations(self, agent_id : str) -> Dict[str, str]:
        """
        The method returns, for a given agent ID, a dictionary mapping the agent ID to the incomplete pairings IDs and to their corresponding public information.
        The dictionary contains only pairing in which one of the two personal agents has not responded yet, and therefore the matching is not completed.

        :param agent_id:
        :return:
        """
        matches : AgentRelations_PersonalAgents = await self.get_matched_personal_agents()

        pending_requests: Dict[str, str] = {}

        for agent_pair, relation_triplet in matches.items():
            if agent_id == agent_pair[0] and relation_triplet in [Relation.ACCEPTED, Relation.REFUSED]:
                if matches[(agent_pair[1], agent_pair[0])] == Relation.UNCONTACTED:
                    pending_requests[agent_pair[1]] = await self.get_public_information(agent_pair[1])

        print(f"ReturningU: {pending_requests}")

        return pending_requests

    async def get_agent_decision(self, sender : str, receiver : str) -> Relation:
        """
        The method returns, given a pair of agent IDs, the personal agent decision.

        :param sender: A string containing the ID of the agent that evaluated the pairing.
        :param receiver: A string containing the ID of the other agent.
        :return: A `Relation` object representing the sender's agent LLM decision.
        """
        async with self._agents_lock:
            return self._matched_agents[sender, receiver][0][self._model_client_name][0]

    async def get_human_decision(self, sender : str, receiver : str) -> Relation:
        """
        The method returns the feedback the corresponding user provided upon a connection request.

        :param sender: The ID of the agent whose user sent the feedback.
        :param receiver: The ID of the agent that originally sent the pairing request.
        :return: A `Relation` object representing the sender's user feedback on the LLM decision.
        """
        async with self._agents_lock:
            return self._matched_agents[sender, receiver][1]

    async def get_user_rules(self, sender: str, receiver: str) -> list:
        """
        The method returns, given a pair of agent IDs, the list of rules that the sender agent's LLM used to evaluate the pairing request.

        :param sender: The ID of the agent that evaluated the pairing request.
        :param receiver: The ID of the agent that sent the pairing request.
        :return: A list containing the rule IDs used by the personal agent to evaluate the pairing.
        """
        async with self._agents_lock:
            return self._matched_agents[sender, receiver][0][self._model_client_name][1]

    async def check_response(self, sender : str, receiver : str, sender_information : str, receiver_policies : str, reasoning : str) -> str:
        """
        The method is called when the orchestrator is actively checking the pairing responses each personal agent gave.
        The method is used to check the LLM's responses and determine if they are correct or if the pairing should be re-evaluated (based on the information available to the orchestrator).

        :param sender: The agent ID of the agent that sent the pairing request.
        :param receiver: The agent ID of the agent that received and evaluated the pairing request.
        :param sender_information: The public information of the `sender`.
        :param receiver_policies: The policies of the `receiver`.
        :param reasoning: The reasoning the `receiver` LLM made based.
        :return: A string containing the orchestrator's LLM answer to the pairing evaluation.
                 It should be considered valid if ("VALID") and consequently saved, or it should be re-evaluated if ("INVALID").
        """
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
        """
        The method is called to send a pairing request from the personal agent sender to the personal agent receiver and to store the receiver response in the `_matched_agents`
        orchestrator's dictionary.

        :param sender: A string containing the agent ID of the agent sending the pairing request.
        :param receiver: A string containing the agent ID of the agent that receives the public information of the sender agent and uses it along with
               its personal information to call its LLM and evaluate it.
               Its LLM answer might be evaluated by the orchestrator agent if the orchestrator is setupped to check the request actively.
        :return: None
        """
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
                llm_decisions : LLMRelations = {}
                for key, value in pair_response.answer.items():
                    llm_decisions[key] = (value, [])

                self._matched_agents[(sender, receiver)] = (llm_decisions, Relation.UNCONTACTED)
            return
        else:
            print(f"ERROR: Unknown answer when handling pairing request to {receiver} from {sender}...")
            return

    async def match_agents(self, user_to_add: str) -> None:
        """
        The method is called to start the pairings after a new personal agent, of ID specified in the parameter `user_to_add`, is created.
        For each user previously registered, a pairing request message is sent with the public information of the new user and a corresponding
        pairing request is sent to the new agent with the public information of all the agents previously registered in the platform.

        :param user_to_add: The ID of a new agent to send the pairing request to.
        :return: None
        """
        registered_agents_copy = await self.get_registered_agents()
        registered_agents_copy.remove(user_to_add)

        matched_agents_copy : AgentRelations_PersonalAgents = await self.get_matched_personal_agents()

        pairing_tasks = []
        for registered_agent in registered_agents_copy:
            # Do the already registered agents accept the pair with the new agent?
            if matched_agents_copy.get((user_to_add, registered_agent)) == Relation.UNCONTACTED:
                pairing_tasks.append(self.pair_agent_with_feedback(user_to_add, registered_agent))

            # Does the new agent accept the pair with the already registered agent?
            if matched_agents_copy.get((registered_agent, user_to_add)) == Relation.UNCONTACTED:
                pairing_tasks.append(self.pair_agent_with_feedback(registered_agent, user_to_add))

        if pairing_tasks:
            await asyncio.gather(*pairing_tasks)

    @message_handler
    async def agent_configuration(self, message: ConfigurationMessage, context: MessageContext) -> None:
        """
        This method is called by the personal agent after the setup is completed to notify the orchestrator that a new personal agent was correctly created.
        The personal agent sends the `ConfigurationMessage` that calls this method. The message contains information from the setup such as the public information
        and the policies extracted from the natural language setup message the user provided.
        This method registers the agent in the orchestrator's data structures and then the orchestrator starts the matching by calling its method `match_agents`.

        :param message: The `ConfigurationMessage` the personal agent sends the orchestrator.
        :param context: A `MessageContext` containing the message contextual information.
        :return: None
        """
        async with self._agents_lock:
            registered = (message.user in self._registered_agents or message.user in self._paused_agents)

        if not registered and message.user == context.sender.key:
            for agent in self._registered_agents:
                if self._matched_agents.get((agent, message.user)) is None:
                    self._matched_agents[(agent, message.user)] : CompleteAgentRelations = {}
                    self._matched_agents[(agent, message.user)] = ({self._model_client_name : (Relation.UNCONTACTED, [])}, Relation.UNCONTACTED)
                    self._matched_agents[(message.user, agent)] = ({self._model_client_name : (Relation.UNCONTACTED, [])}, Relation.UNCONTACTED)

            self._registered_agents.add(message.user)
            self._agent_information[message.user] = (message.user_information, message.user_policies)

            await self.match_agents(message.user)

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
        """

        The method is called by either the personal agent or the FastAPI directly to query the orchestrator agent data structures.
        The method is called when the runtime sends a message of type `GetRequest` to the orchestrator agent.
        The message contains a `request_type` parameter that it is used in the method to determine the information wanted.
        This method is used as an external data access way for the orchestrator agent.

        :param message: A `GetRequest` message containing a request to query the orchestrator's data structures.
        :param context: A `MessageContext` containing the message contextual information.
        :return: A `GetResponse` object containing the answer to the received request.
        """
        answer = GetResponse(request_type=message.request_type)
        if RequestType(message.request_type) == RequestType.GET_AGENT_RELATIONS:
            answer.agents_relation = await self.get_matched_personal_agents()
        elif RequestType(message.request_type) == RequestType.GET_AGENT_RELATIONS_FULL:
            answer.agents_relation_full = await self.get_matched_agents_full()
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
        """
        The method is called upon receiving an `ActionRequest` message. The message is sent by a personal agent, after it receives a request
        to pause, resume, delete or reset its personal agent.

        As the orchestrator contains in its data structure information by that agent that might become inconsistent, the `ActionRequest`
        is forwarder to the orchestrator so that it can change its data structures and keep consistencies between agents.

        :param message: An `ActionRequest` containing a user request to change its personal agent state.
        :param context: A `MessageContext` containing the message contextual information.
        :return: None
        """
        if ActionType(message.action_type) == ActionType.PAUSE_AGENT:
            await self.pause_agent(message.user)
        elif ActionType(message.action_type) == ActionType.RESUME_AGENT:
            await self.resume_agent(message.user)
        elif ActionType(message.action_type) == ActionType.DELETE_AGENT:
            await self.reset_agent_pairings(message.user)
            await self.delete_agent(message.user)
        elif ActionType(message.action_type) == ActionType.RESET_AGENT:
            await self.reset_agent_pairings(message.user)
            await self.delete_agent(message.user)

        await log_event(
            event_type="agent_status_change",
            source=message.user,
            data=ActionRequest(
                action_type=message.action_type,
            )
        )

    @message_handler
    async def human_in_the_loop(self, message: FeedbackMessage, context: MessageContext) -> Status:
        """
        The method is called by the personal agent after the runtime sends to the Orchestrator a `FeedbackMessage`.
        The method is called when a user sends feedback for an agent pairing and the orchestrator consequently updates its data structures to save such new information.

        :param message: A `FeedbackMessage` containing feedback provided by a user on a personal connection.
        :param context: A `MessageContext` containing the message contextual information.
        :return: A status indicating whether the method was successful or not.
        """
        print("FEEDBACK RECEIVED!")
        async with self._agents_lock:
            key = (message.sender, message.receiver)
            if key not in self._matched_agents:
                print(f"No matching record found for {message.sender}->{message.receiver}")
                return Status.FAILED

            if Relation(message.feedback) not in [Relation.USER_REFUSED, Relation.USER_ACCEPTED]:
                print(f"Received an illegal feedback value: {message.feedback}.\n")
                return Status.FAILED

            self._matched_agents[key] = (
                self._matched_agents[key][0],
                message.feedback
            )

        await log_event(
            event_type="human_feedback",
            source=message.sender,
            data=message
        )
        return Status.COMPLETED
