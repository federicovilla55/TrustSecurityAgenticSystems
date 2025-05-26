import json
from typing import Dict, List, Optional, Tuple, Set, Any, Coroutine
from autogen_core import AgentId, MessageContext, RoutedAgent, message_handler, type_subscription, TopicId, DefaultTopicId
from autogen_core.model_context import BufferedChatCompletionContext
from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage
import asyncio
import logging

from src.database import get_database, get_user, log_event

from src.enums import  Status, ActionType, Relation, RequestType

from src.models import (UserInformation, SetupMessage, ConfigurationMessage, PairingRequest,
                        PairingResponse, GetRequest, GetResponse, ModelUpdate)
from ..models.messages import ActionRequest, InitMessage

from ..utils import extract_section, remove_chain_of_thought, separate_categories, extract_json

def default_rules(value: int) -> str:
    """
    The function is a helper function to generate the default rules for the user.
    :param value: A value indicating the default rule to be used. The possible values are: 0, 1, 2, 3.
    \n- `0`: Connect with anyone sharing common interests (e.g., hobbies, projects) or similar job title/role.
    \n- `1`: Connect with users in the same industry (e.g., tech, healthcare).
    \n- `2`: Connect only with users from the same organization/company.
    \n- `3`: Connect with users from the same organization AND similar job title/role (e.g., 'Senior Engineer at Microsoft').
    \n- any other value: interpreted as the emtpy string "".

    :return: A string containing the default rule for the agent.
    """
    default_rule = "USE THE FOLLOWING DEFAULT RULES:\n- "
    if value == 0:
        default_rule += "Connect with anyone sharing common interests (e.g., hobbies, projects) or similar job title/role."
    elif value == 1:
        default_rule +=  "Connect with users in the same industry (e.g., tech, healthcare)."
    elif value == 2:
        default_rule +=  "Connect only with users from the same organization/company."
    elif value == 3:
        default_rule +=  "Connect with users from the same organization AND similar job title/role (e.g., 'Senior Engineer at Microsoft')."
    else:
        default_rule = ""

    return default_rule

class MyAgent(RoutedAgent):
    """
    MyAgent class defines a personal agent, used by each user to connect with other users.
    The agent is defined as a subclass of the routed agent, the base AutoGen class used to create LLM-powered agents.
    MyAgent is instructed to pair with other agents based on information its corresponding user provides.
    The agent is registered at runtime and it is created by a user when completing the setup via a `SetupMessage`.
    The agent remains active until it is paused via a `PauseMessage` or deleted via a `DeleteMessage`.
    The agent communicates with a central agent, the orchestrator, which shares the public information of the posisble pairing.
    Each pairing request is evaluated by the agent's LLMs, and the agent accepts or rejects the connection based on each model's response.
    The information the agent uses to decide whether to accept or reject a connection is the user's public information,
    private information and pairing policies and preferences.
    """
    def __init__(self, model_client: ChatCompletionClient, processing_model_clients : [str, ChatCompletionClient] = {}):
        """
        Personal Agent (MyAgent) constructor. This method initializes the MyAgent object and its attributes.
        :param model_client: A ChatCompletionClient object is used to interact with the LLM model.
        This attribute is the main LLM model the agen will use to extract and divide user-provided information during the setup phase.
        :param processing_model_clients: A dictionary containing the names of LLMs and their corresponding ChatCompletionClient objects.
        The LLMs inside the dictionary will be each used to evaluate the pairing requests sent by the orchestrator,
        this enables to evaluate each LLM model independently.
        """

        super().__init__("my_agent")
        if processing_model_clients is None:
            processing_model_clients = {}
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

        self._processing_model_clients: Dict[str, Tuple[bool, ChatCompletionClient]] = {
            name: (True, client)
            for name, client in processing_model_clients.items()
        }

    def update_model_clients(self, updates: Dict[str, bool]) -> None:
        """
        The method is used to update which LLMs to be used to evaluate the pairing requests sent by the orchestrator. The method provides
        for each model client name a boolean value indicating whether to use it or not.
        :param updates: A dictionary containing the names of the LLMs and their corresponding boolean values, indicating whether to use them or not..
        :return: None
        """
        for model_name, new_bool in updates.items():
            if model_name in self._processing_model_clients:
                _, client = self._processing_model_clients[model_name]
                self._processing_model_clients[model_name] = (new_bool, client)

        print(f"Updated models: {self.get_model_clients()}")

    def get_model_clients(self) -> Dict[str, bool]:
        """
        The method is used to get the list of LLMs and their corresponding boolean values,
        indicating whether they are selected to be used to evaluate the pairing requests sent by the orchestrator.
        :return: A dictionary containing the names of the LLMs and their corresponding boolean values,
        indicating whether they are selected to be used to evaluate the pairing requests sent by the orchestrator..
        """
        return {name: value[0] for name, value in self._processing_model_clients.items()}

    def get_public_information(self) -> str:
        """
        Returns a string containing the agent public information.
        :return: A string containing the agent public information.
        """
        return " ".join(item['content'] for item in self._public_information)
    
    def get_private_information(self) -> str:
        """
        Returns a string containing the agent private information.
        :return: A string containing the agent private information.
        """
        return " ".join(item['content'] for item in self._private_information)

    def get_policies(self) -> str:
        """
        Returns a string containing the agent defined policies.
        :return: A string containing the agent defined policies.
        """
        return " ".join(item['content'] for item in self._policies)

    def is_paused(self) -> bool:
        """
        Returns True if the agent is paused, False otherwise.
        :return: A boolean value indicating whether the agent is paused or not.
        """
        return self._paused

    def is_setup(self) -> bool:
        """
        Returns True if the agent has completed the setup, False otherwise.
        :return: A boolean value indicating whether the agent has completed the setup or not.
        """
        return (self._user is not None or self._policies is not None or
                self._public_information is not None or self._private_information is not None)

    async def evaluate_connection(self, context, prompt, requester : str) -> PairingResponse:
        """
        The method is used to evaluate a connection request sent by the orchestrator to the personal agent.
        This method calls each of the LLMs selected to be used to evaluate the connection request and sends them the prompt
        containing the requester public information and the personal information (public, private and policies) of the agent.
        Each LLM's response is evaluated and the result is returned as a `PairingResponse` object.
        :param context: A `MessageContext` containing the message contextual information.
        :param prompt: The prompt containing the requester public information and the personal information (public, private and policies) of the agent.
        :param requester: The agent ID of the requester.
        :return: A PairingResponse object containing the response from each LLM model and the result of the evaluation.
        """
        pairing_response_status: dict[str, Relation] = {}
        result = ""

        for model_name, (is_active, model_client) in self._processing_model_clients.items():
            if not is_active:
                continue

            llm_answer = await model_client.create(
                messages=[self._system_message, UserMessage(content=prompt, source=self._user),] +
                          await self._model_context.get_messages() +
                          await self._model_context_dict[requester].get_messages(),
                cancellation_token=context.cancellation_token,
            )

            result = remove_chain_of_thought(llm_answer.content)
            first_line = result.splitlines()[0].upper()

            if 'REJECT' in first_line:
                pairing_response_status[model_name] = Relation.REFUSED
            elif 'ACCEPT' in first_line:
                pairing_response_status[model_name] = Relation.ACCEPTED
            else:
                print(f"ERROR: Unknown answer from model {model_name}")
                pairing_response_status[model_name] = Relation.REFUSED

        return PairingResponse(pairing_response_status, result)

    async def notify_orchestrator(self, action_type : ActionType) -> Status:
        """
        The method is called upon receiving an action request from the user, so a request to either pause, resume or delete the agent.
        :param action_type: An enum value indicating the type of action requested by the user (`PAUSE_AGENT`, `RESUME_AGENT`, `DELETE_AGENT`, `RESET_AGENT`).).
        :return: A `Status` object indicating whether the action was successful or not.
        """
        message = ActionRequest(
            request_type=action_type.value,
            user=self._user,
        )

        await self.publish_message(
            message=message, topic_id=TopicId("orchestrator_agent", "default")
        )

        return Status.COMPLETED

    @message_handler
    async def handle_init(self, message: InitMessage, context: MessageContext) -> Status:
        """
        The method is called upon receiving an `InitMessage` from the user.
        The `InitMessage` is called as a user explicit request to create the agent.
        :param message: An (empty) InitMessage
        :param context: A `MessageContext` containing the message contextual information.
        :return: A `Status` object indicating whether the action was successful or not.
        """
        return Status.COMPLETED

    @message_handler
    async def handle_setup(self, message: SetupMessage, context: MessageContext) -> Status:
        """
        The method is called upon receiving a `SetupMessage` from the user.
        The method is therefore called when a user provided a natural language description of their personal information and policies and therefore their
        corresponding agent is created.
        This message creates the personal agent if it was not previously created, therefore upon registering a user
        calls the `setup_agent` method and creates the personal agent using this method.
        In the `SetupMessage` public information, private information and policies are all provided as a single natural language string. Therefore
        in this method the agent calls the main LLM, the one defined in `_init()_` and saved as `self._model_client`, to generate a JSON formatted
        list containing public information, policies and private information splitted in three sections.
        Upon splitting such personal information, the agent shares with the orchestrator the public information and policies, notifying the central agent about the
        successful personal agent creation and therefore starting the pairing process.
        :param message: The `SetupMessage` object containing the user's personal information, policies and default rule index.
        :param context: A `MessageContext` containing the message contextual information.
        :return: A `Status` object indicating whether the action was successful or not.
        """

        if self.is_setup():
            return Status.REPEATED

        username = message.user
        self._user = message.user
        policies = None
        public_information = None
        private_information = None
        #print(f"'{self.id}' Received setup message {message}")

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
                    {default_rules(message.default_value)}
                    
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

        llm_answer = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt_information, source=username)],
            cancellation_token=context.cancellation_token,
        )


        await self._model_context.add_message(UserMessage(content=llm_answer.content, source=username))

        prompt = f"""Use the previous messages to generate a JSON formatted list of public policies provided by the user.
                    Those rules must have a "rule_ID" field (composed of "info_" and a number) and a "content" field.
                    [{{"rule_ID": "info_1", "content": "..."}}, ...]"""

        while policies is None:
            llm_answer = await self._model_client.create(
                messages = [UserMessage(content=prompt, source=username)] + await self._model_context.get_messages(),
                cancellation_token=context.cancellation_token,
            )

            policies = extract_json(llm_answer.content)

        prompt = f"""Use the previous messages to generate a JSON well-formatted list of public information provided by the user.
                            Those information must have a "info_ID" field (composed of "pub_" and a number) and a "content" field.
                            [{{"rule_id": "pub_1", "content": "..."}}, ...]"""

        while public_information is None:
            llm_answer = await self._model_client.create(
                messages = [UserMessage(content=prompt, source=username)] + await self._model_context.get_messages(),
                cancellation_token=context.cancellation_token,
            )

            public_information = extract_json(llm_answer.content)

        prompt = f"""Use the previous messages to generate a JSON well-formatted list of private information provided by the user.
                            Those information must have a "info_ID" field (composed of "priv_" and a number) and a "content" field.
                            [{{"info_ID": "priv_1", "content": "..."}}, ...]"""

        while private_information is None:
            llm_answer = await self._model_client.create(
                messages = [UserMessage(content=prompt, source=username)] + await self._model_context.get_messages(),
                cancellation_token=context.cancellation_token,
            )

            private_information = extract_json(llm_answer.content)


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

        '''print(f"{'='*20}\n{self._user} POLICIES: {self._policies}")
        print(f"{self._user} PUBLIC INFORMATION: {self._public_information}\n")
        print(f"{self._user} PRIVATE INFORMATION: {self._private_information}\n{'=' * 20}\n")'''

        self._user = username
        self._policies = policies
        self._public_information = public_information
        self._private_information = private_information

        configuration_message = ConfigurationMessage(
            user=self._user,
            user_policies=self._policies,
            user_information= self._public_information,
        )

        db = get_database()
        cursor = db.cursor()
        cursor.execute(
            """UPDATE user_data 
            SET public_information = ?,
                private_information = ?,
                policies = ?
            WHERE username = ?""",
            (
                json.dumps(self._public_information),
                json.dumps(self._private_information),
                json.dumps(self._policies),
                self._user,
            )
        )
        db.commit()

        await log_event(
            event_type="agent_configuration",
            source=self._user,
            data=UserInformation(
                username=self._user,
                public_information=self._public_information,
                policies=self._policies,
                private_information=self._private_information,
                paused=self.is_paused()
            )
        )

        await self.publish_message(
            configuration_message, topic_id=TopicId("orchestrator_agent", "default")
        )

        print("SETUP COMPLETED")

        return Status.COMPLETED

    @message_handler
    async def handle_pairing_request(self, message: PairingRequest, context: MessageContext) -> PairingResponse:
        """
        Handles an incoming pairing request and decides based on the sender public information and the receiver public and personal information and policies.
        :param message: A pairing request send by the orchestrator on behalf of another MyAgent that wants to connect.
        :param context:
        :return: A `PairingResponse` object, containing a response to the pairing request.
        """
        #print(f"'{self.id}' Received pairing request from '{message.user}'")
        if not self.is_setup() or self.is_paused():
            return PairingResponse(
                {model_name: Relation.UNCONTACTED.value for model_name in self._processing_model_clients.keys()},
                "MyAgent is paused or its setup is incomplete."
            )

        if message.receiver != "" and message.receiver != self._user:
            return PairingResponse(
                {model_name: Relation.UNCONTACTED.value for model_name in self._processing_model_clients.keys()},
                "MyAgent is not the correct receiver fot the message"
            )

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

        response = await self.evaluate_connection(context, prompt, message.requester)

        return response

    @message_handler
    async def handle_get_request(self, message : GetRequest, context: MessageContext) -> UserInformation | GetResponse:
        """
        Handles an incoming get request asking for some of the user personal information.
        :param message: The get request containing the type of information requested.
        :param context:
        :return: The user information that was requested.
        """
        answer = UserInformation(
            public_information={},
            private_information={},
            policies={},
            paused=self.is_paused(),
            username=""
        )

        if not self.is_setup():
            answer.is_setup = False
            return answer

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
        elif RequestType(message.request_type) == RequestType.GET_MODELS:
            return GetResponse(
                request_type=RequestType.GET_MODELS,
                models=self.get_model_clients(),
            )

        return answer


    @message_handler
    async def handle_action_request(self, message : ActionRequest, context: MessageContext) -> Status:
        """
        Handles an incoming action request asking to either pause, resume or delete the agent.
        :param message: The request containing the type of action the agent should do.
        :param context:
        :return: A status, indicating if the operation was successfully done or not.
        """
        operation = Status.FAILED

        if self.is_setup() or True:
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
            elif ActionType(message.request_type) == ActionType.RESET_AGENT:
                self._paused = False
                operation = await self.notify_orchestrator(ActionType.RESET_AGENT)

        return operation

    @message_handler
    async def update_model(self, message : ModelUpdate, context : MessageContext) -> Status:
        """
        The method is called upon receiving a `ModelUpdate` message from the orchestrator. It is called
        when a user updates the list of LLMs to be used when evaluating a pairing requests.
        :param message: The `ModelUpdate` message containing the list of LLMs and a boolean value indicating whether the user wants to use the default LLMs or not.
        :param context: A `MessageContext` containing the message contextual information.
        :return: A `Status` object indicating whether the action was successful or not.
        """
        self.update_model_clients(message.models)

        return Status.COMPLETED

    @message_handler
    async def change_user_information(self, message : UserInformation, context : MessageContext) -> Status:
        """
        Handles a request to change the public and private information and policies of the agent. This requests comes from the user directly modifying those policies or informations.
        :param message: The `UserInformation` message contains the new public and private information and policies of the agent.
        :param context: A `MessageContext` containing the message contextual information.
        :return: A `Status` object indicating whether the action was successful or not.
        """
        self._policies = message.policies
        self._private_information = message.private_information
        self._public_information = message.public_information

        await log_event(
            event_type="change_agent_information",
            source=self._user,
            data=UserInformation(
                username=self._user,
                public_information=self._public_information,
                policies=self._policies,
                private_information=self._private_information,
                paused=self.is_paused(),
            )
        )

        if message.reset_connections:
            new_conf_message = ConfigurationMessage(
                user=self._user,
                user_information=self._public_information,
                user_policies=self._policies,
            )
            await self.publish_message(
                new_conf_message, topic_id=TopicId("orchestrator_agent", "default")
            )


        return Status.COMPLETED