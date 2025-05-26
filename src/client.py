from typing import Optional, Dict

from src.models.messages import InitMessage, GetResponse
from src.runtime import Runtime
from src.enums import Status, ActionType, AgentRelations_PersonalAgents, RequestType, Relation
from src.models import (SetupMessage, ActionRequest, UserInformation,
                        GetRequest, FeedbackMessage, ModelUpdate)
import httpx

class Client:
    """
    The Client class is the interface used by the user to interact with its personal agent
    or the central (orchestrator) agent.
    The user calls this class directly when it uses the FastAPI framework.
    """

    def __init__(self, username : str):
        """
        Client class constructor.
        :param username: Username of the user.
        """
        self._username = username
        self._token : Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """
        Async context manager entry point. Used to initialize the asynchronous HTTP client.
        :return: None
        """
        self._client = httpx.AsyncClient()
        return self

    async def init_agent(self):
        """
        Called to explicitly initialize the personal agent.
        As in AutoGen agents are initialized automatically when the user sends a
        message, this method is currently not used.
        :return: None
        """
        await Runtime.send_message(InitMessage(), "my_agent", self._username)

    async def setup_user(self, user_content: str, default_value : int = 1) -> Status:
        """
        Method called to set up the personal agent by sending a `SetupMessage` with user-provided information.
        :param user_content: User-provided information.
        :param default_value: Value for the default user policies.
        :return: A status indicating whether the setup was successful or not.
        """
        return await Runtime.send_message(SetupMessage(content=user_content, user=self._username, default_value=default_value), "my_agent", self._username)

    async def pause_user(self) -> Status:
        """
        Method called to pause the personal agent by sending an `ActionRequest` with the PAUSE_AGENT action type.
        :return: A status indicating whether the setup was successful or not.
        """
        return await Runtime.send_message(
            message=ActionRequest(request_type=ActionType.PAUSE_AGENT.value, user=self._username),
            agent_type="my_agent", agent_key=self._username
        )


    async def resume_user(self) -> Status:
        """
        Method called to resume the personal agent by sending an `ActionRequest` with the RESUME_AGENT action type.
        :return: A status indicating whether the setup was successful or not.
        """
        return await Runtime.send_message(
            message=ActionRequest(request_type=ActionType.RESUME_AGENT.value, user=self._username),
            agent_type="my_agent",
            agent_key=self._username
        )

    async def delete_user(self) -> Status:
        """
        Method called to delete the personal agent by sending an `ActionRequest` with the DELETE_AGENT action type.
        :return: A status indicating whether the setup was successful or not.
        """
        return await Runtime.send_message(
            message=ActionRequest(request_type=ActionType.DELETE_AGENT.value, user=self._username),
            agent_type="my_agent",
            agent_key=self._username
        )

    async def get_agent_all_relations(self) -> AgentRelations_PersonalAgents:
        """
        The method asks the orchestrator agent for the user's agent relations and returns them.
        :return: The agent relations established by the user.
        """
        matches : GetResponse = (
            await Runtime.send_message(
                    message=GetRequest(request_type=RequestType.GET_PERSONAL_RELATIONS.value, user=self._username),
                    agent_type="orchestrator_agent",
            )
        )

        return matches.agents_relation

    async def get_human_pending_relations(self) -> Dict[str, str]:
        """
        This method asks the orchestrator agent for the user's relations that are completed, so in which both agents have
        decided for the pairings but the users have not expressed any feedback, and returns them.
        :return: A dictionary with a string pair containing the username of the two users in the un-feedback-ed relations.
        """
        matches : GetResponse = (
            await Runtime.send_message(
                message=GetRequest(request_type=RequestType.GET_PENDING_HUMAN_APPROVAL.value, user=self._username),
                agent_type="orchestrator_agent",
            )
        )

        return matches.users_and_public_info

    async def get_agent_established_relations(self) -> Dict[str, str]:
        """
        The method asks the orchestrator agent for the user's established relations,
        so in which both agent and humans have approved it and returns them.
        :return: A dictionary containing a string pair with the couple of usernames the user is in pair with.
        """
        matches : GetResponse = (
            await Runtime.send_message(
                message=GetRequest(request_type=RequestType.GET_ESTABLISHED_RELATIONS.value, user=self._username),
                agent_type="orchestrator_agent",
            )
        )

        return matches.users_and_public_info

    async def get_agent_sent_decisions(self) -> Dict[str, str]:
        """
        This method returns the relations that the user has sent and that have not been answered yet by the other agent.
        :return: A dictionary containing a string pair with the couple of usernames the user sent a pairing request to.
        """
        matches : GetResponse = (
            await Runtime.send_message(
                message=GetRequest(request_type=RequestType.GET_UNFEEDBACK_RELATIONS.value, user=self._username),
                agent_type="orchestrator_agent",
            )
        )

        return matches.users_and_public_info

    async def get_pairing(self) -> AgentRelations_PersonalAgents:
        """
        The method returns the relations the agents have made and that the humans have confirmed.
        :return: The agent relations established by the user.
        """
        pairings : GetResponse = (
            await Runtime.send_message(
                message=GetRequest(request_type=RequestType.GET_PERSONAL_RELATIONS.value, user=self._username),
                agent_type="orchestrator_agent",
            )
        )

        return pairings.agents_relation

    async def get_agent_failed_relations(self):
        """
        *Not Implemented*
        This method returns the relations that the user's agent has refused and therefore cannot be evaluated by the user.
        Might be useful if the user wants to give a feedback to them too.
        :return:
        """
        pass

    async def get_public_information(self) -> dict:
        """
        The method asks the personal agent for its public information and returns it.
        :return: A dictionary containing the public information of the user.
        """
        get_response : UserInformation = (
            await Runtime.send_message(
                message=GetRequest(request_type=RequestType.GET_PUBLIC_INFORMATION.value, user=self._username),
                agent_type="my_agent",
                agent_key=self._username
            )
        )

        return get_response.public_information

    async def get_private_information(self) -> dict:
        """
        The method asks the personal agent for its private information and returns it.
        :return: A dictionary containing the private information of the user.
        """
        get_response : UserInformation = (
            await Runtime.send_message(
                message=GetRequest(request_type=RequestType.GET_PRIVATE_INFORMATION.value, user=self._username),
                agent_type="my_agent",
                agent_key=self._username
            )
        )

        return get_response.private_information
    
    async def get_policies(self) -> dict:
        """
        The method asks the personal agent for its policies and returns it.
        :return: A dictionary containing the pairing policies of the user.
        """
        get_response : UserInformation = (
            await Runtime.send_message(
                message=GetRequest(request_type=RequestType.GET_POLICIES.value, user=self._username),
                agent_type="my_agent",
                agent_key=self._username
            )
        )
        return get_response.policies

    async def get_models(self) -> dict:
        """
        The method asks the personal agent for the available LLM models and returns them.
        :return: A dictionary containing the available LLM models of the user.
        In the dictionary the keys are the model names and the values are the model descriptions.
        """
        get_model_request = GetRequest(
            request_type=RequestType.GET_MODELS.value,
            user=self._username,
        )
        get_models : GetResponse = (
            await Runtime.send_message(
                message=get_model_request,
                agent_type="my_agent",
                agent_key=self._username
            )
        )

        return get_models.models

    async def update_models(self, models : dict) -> Status:
        """
        The method is called to update the personal agent's available LLM models.
        This method overwrites the previous available models so it should be called
        with all the models the user is interested in using.
        :param models: A dictionary containing the available LLM models of the user.
        The keys are the model names and the values are the model descriptions.
        :return: A status indicating whether the update was successful or not.
        """
        return await Runtime.send_message(
            message=ModelUpdate(models),
            agent_type="my_agent",
            agent_key=self._username
        )

    async def get_information(self) -> dict:
        """
        The method is called to get all the user and user's agent information.
        That information is the policies, public information, private information,
        whether the user's agent is setUp or not, and whether the user's agent is paused or not.
        :return: A dictionary containing the requested information.
        """
        get_response : UserInformation = (
            await Runtime.send_message(
                message=GetRequest(request_type=RequestType.GET_USER_INFORMATION.value, user=self._username),
                agent_type="my_agent",
                agent_key=self._username
            )
        )

        return {
            'policies' : get_response.policies,
            'public_information' : get_response.public_information,
            'private_information' : get_response.private_information,
            'isSetup' : get_response.is_setup,
            'paused' : get_response.paused,
        }
    
    async def change_information(self, public_information : dict, private_information : dict, policies : dict, reset : bool = False) -> Status:
        """
        The method is called to change the user's policies, public information, private information.
        A boolean flag can be used to reset the user's previously made agent connections after changing the user information.
        :param public_information: A dictionary containing the public information of the user. The keys are the information names and the values are the information descriptions.
        :param private_information: A dictionary containing the private information of the user. The keys are the information names and the values are the information descriptions.
        :param policies: A dictionary containing the pairing policies of the user. The keys are the policy names and the values are the policy descriptions.
        :param reset: A boolean indicating whether to reset the user's previously made agent connections after changing the user policies.
        :return: A status indicating whether the change was successful or not.
        """
        if reset:
            await Runtime.send_message(
                message=ActionRequest(request_type=ActionType.RESET_AGENT.value, user=self._username),
                agent_type="my_agent",
                agent_key=self._username,
            )

        return await Runtime.send_message(
            message=UserInformation(
                public_information=public_information,
                private_information=private_information,
                policies=policies,
                username=self._username,
                reset_connections = reset,
            ),
            agent_type="my_agent",
            agent_key=self._username
        )

    async def send_feedback(self, receiver : str, accepted : bool) -> Status:
        """
        This method is called when a user sends a feedback for a pairing with the `receiver` agent.
        This method sends a message containing the feedback information to the orchestrator agent.
        :param receiver: The username of the other agent the user is sending the feedback to.
        :param accepted: A boolean flag indicating whether the human accepted the pairing or not.
        :return: A status indicating whether the feedback was sent successfully or not.
        """
        feedback : Relation
        if accepted:
            feedback = Relation.USER_ACCEPTED
        else:
            feedback = Relation.USER_REFUSED

        sender = self._username

        return await Runtime.send_message(
            message=FeedbackMessage(
                sender=sender,
                receiver=receiver,
                feedback=feedback.value,
            ),
            agent_type="orchestrator_agent",
        )

    async def save_configuration(self):
        """
        *Not Yet Implemented*
        This method is called to save the user's configuration in a file or database to be later loaded and ensure persistency.
        :return: None
        """
        pass

    async def load_configuration(self):
        """
        *Not Yet Implemented*
        This method is called to load the user's configuration from a file or database.
        :return: None
        """
        pass

    async def user_authentication(self, password: str):
        """
        This method is called to authenticate the user with the fast api server
        by calling the /token endpoint of the server to get a JWT token..
        :param password: The user password.
        :return:
        """
        # Call /token endpoint to get JWT
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "/api/token",
                data={"username": self._username, "password": password}
            )
            response.raise_for_status()
            self._token = response.json()["access_token"]

    @property
    def headers(self) -> Dict[str, str]:
        """
        The property returns the headers needed to authenticate the user with the fast api server.
        :return: A dictionary containing the headers needed to authenticate the user with the fast api server.
        """
        return {"Authorization": f"Bearer {self._token}"}