import os
from dataclasses import asdict

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext

from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
import logging
import asyncio
import uvicorn
import secrets
import json

from aiosqlite import connect
from src.client import Client
from src.models.messages import RequestType
from src.enums.enums import Status, ModelType
from src.runtime import Runtime, get_model, register_my_agent, register_orchestrator
from src.database import DATABASE_PATH, get_user, create_user, get_database, init_database, clear_database

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
TOKEN_DURATION = timedelta(hours=1)

clients = {}

@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """
    The function is called when the FastAPI app starts. Database and runtime are initialized.
    :param app: The FastAPI app object.
    :return: None
    """
    init_database()

    # Remove the following two lines to keep the saved users in the database and not re-initialize it every time.
    clear_database()
    init_database()

    # Initialize your resources and perform your startup tasks:
    model_name = "meta-llama/Llama-3.3-70B-Instruct"
    model_name = "qwen2.5"
    model_client_my_agent = get_model(
        model_type=ModelType.OLLAMA, model=model_name, temperature=0.7
    )
    model_client_orchestrator = get_model(
        model_type=ModelType.OLLAMA, model=model_name, temperature=0.5
    )

    model_name2 = "swissai/apertus3-70b-2.5T-sft"
    second_model = get_model(
        model_type=ModelType.OLLAMA, model=model_name2, temperature=0.7
    )

    model_name3 = "Qwen/Qwen3-8B"
    third_model = get_model(
        model_type=ModelType.OLLAMA, model=model_name3, temperature=0.7
    )

    try:
        # Start the runtime and register your agents
        Runtime.start_runtime()
        await register_my_agent(model_client_my_agent, {
            model_name : model_client_my_agent,
            model_name2 : second_model,
            model_name3 : third_model,
        })
        await register_orchestrator(model_client_orchestrator, model_name)
        # Everything is ready: yield control to start serving requests
        yield
        # Optionally, you can print a success message here if desired:
        print("Startup completed successfully.")
    except (RuntimeError, JWTError) as e:
        # If something goes wrong during startup, log the error and re-raise it
        print(f"FOUND ERROR during startup: {e}")
        raise e
    finally:
        # Shutdown logic: clean up all resources whether startup succeeded or an error occurred later
        await Runtime.stop_runtime()
        await Runtime.close_runtime()
        await model_client_my_agent.close()
        await model_client_orchestrator.close()
        print("Cleanup completed during shutdown.")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

lock = asyncio.Lock()

class Token(BaseModel):
    """
    The Token class is used to define the token as a string representing the access token and a string representing the token type.
    """
    access_token: str
    token_type: str

def create_access_token(data: dict) -> str:
    """
    The function is called to create an access token. The token is created as a JWT from a specified secret key.
    
    :param data: A dictionary with user information.
    :return: A string representing the access token.
    """
    to_encode = data.copy()
    expire = datetime.now() + TOKEN_DURATION
    to_encode.update({
        "exp": expire,
        "sub": str(data["sub"]),
        "type": "access"
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_client(username : str) -> Client | None:
    """
    The function is called to get a client object given a username.

    :param username: A string representing the username.
    :return: A Client object or `None` if the username is not found.
    """
    async with lock:
        if username in clients:
            return clients[username]
        else:
            print("USER NOT FOUND!")
            return None

async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    The function is called to get the current user given a token. (This ensures that the user sending requests is authenticated and has the right permissions)

    :param token: A string representing the token.
    :return: A string representing the username the token is associated with.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    db = get_database()
    user = get_user(db, username)

    if not user:
        raise credentials_exception


    return username

@app.get("/")
async def read_root():
    """
    The function is called to handle the root route.

    :return: A dictionary containing a message indicating that the root route was accessed.
    """
    return {"message": "Hello, world!"}

@router.post("/register")
async def register(registration_data_json : dict) -> dict:
    """
    The function is called to register a new user.

    :param registration_data_json: A dictionary containing the username and password for the new user.
    :return: A dictionary containing a message indicating that the user was registered successfully.
    """
    db = get_database()
    existing_user = get_user(db, registration_data_json["username"])

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username already registered",
        )

    create_user(
        db,
        registration_data_json["username"],
        pwd_context.hash(registration_data_json["password"])
    )

    async with lock:
        clients[registration_data_json["username"]] = Client(registration_data_json["username"])

    return {"status" : f"{registration_data_json['username']} is now registered.\nRedirecting to Dashboard..."}


@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dict:
    """
    The function is called to login a user given their username and password.
    The function returns an access token that the user would then use to authenticate to other API endpoints.

    :param form_data: A OAuth2PasswordRequestForm object containing the username and password of the user.
    :return: A dictionary containing an access token and a token type.
    """
    db = get_database()
    user = get_user(db, form_data.username)
    if user is None or not pwd_context.verify(form_data.password, user[1]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "access_token": create_access_token(data={"sub": user[0]}),
        "token_type": "bearer"
    }

@router.post("/setup")
async def setup_user(setup_json: dict, user_token_data: str = Depends(get_current_user)) -> dict:
    """
    The function is called to setup a user and calling the methods to call its corresponding personal agent.

    :param setup_json: A dictionary containing the username, setup string message, and chosen default policies value.
    :param user_token_data: A string representing the access token of the user.
    :return: A dictionary containing a message indicating that the user was setup successfully.
    """
    if setup_json["user"] != user_token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username",
        )

    client = await get_client(setup_json["user"])

    clients[setup_json["user"]] = client

    operation : Status = await client.setup_user(setup_json["content"], int(setup_json["default_value"]))

    if operation != Status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setup failed"
        )

    return {"status": "setup_complete"}

@router.post("/change_information")
async def change_information(information_json: dict, user_token_data: str = Depends(get_current_user)) -> dict:
    """
    The function is called to change the information of a user.

    :param information_json: A dictionary containing the new information of the user (personal information, private information, policies and reset flag).
    :param user_token_data: A string representing the access token of the user.
    :return: A dictionary indicating that the information was changed successfully.
    """
    db = get_database()
    user = get_user(db, information_json["user"])

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )

    if ("public_information" not in information_json.keys() or "private_information" not in information_json.keys()
            or "policies" not in information_json.keys()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request Incomplete"
        )

    if information_json["user"] != user_token_data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot setup another user"
        )

    client = Client(information_json["user"])

    reset_connections = ("reset" not in information_json) or (information_json["reset"] == 1)

    operation : Status = await client.change_information(
        information_json["public_information"],
        information_json["private_information"],
        information_json["policies"],
        reset_connections
    )

    if operation != Status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operation failed"
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
            json.dumps(information_json["public_information"]),
            json.dumps(information_json["private_information"]),
            json.dumps(information_json["policies"]),
            user_token_data
        )
    )
    db.commit()


    return {"status": "Information updated."}

@router.get("/relations")
async def get_relations(current_user: str = Depends(get_current_user)) -> dict:
    """
    The function is called to get the relations of a user given its username.

    :param current_user: A string representing the username.
    :return: A dictionary containing the full relation data structure with the relations of the user.
    """
    client = await get_client(current_user)

    relations = await client.get_agent_all_relations()

    response = {'relations': relations}

    return response

@router.get("/get_pending_relations")
async def get_pending_relations(current_user: str = Depends(get_current_user)) -> dict:
    """
    The function is called to get the pending relations of a user given its username.

    :param current_user: The username of the user.
    :return: A dictionary containing the pending relations of the user.
    """
    client = await get_client(current_user)


    relations = await client.get_human_pending_relations()

    response = {'relations': relations}

    return response

@router.get("/get_established_relations")
async def get_established_relations(current_user: str = Depends(get_current_user)) -> dict:
    """
    The function is called to get the established relations of a user given its username.
    The established relations are the personal relations accepted by both agents and confirmed by the user.

    :param current_user: The username of the user.
    :return: A dictionary containing the established relations of the user.
    """
    client = await get_client(current_user)

    relations = await client.get_agent_established_relations()

    response = {'relations': relations}

    return response

@router.get("/get_agent_sent_decision")
async def get_agent_sent_decision(current_user: str = Depends(get_current_user)) -> dict:
    """
    The method is called to get the pairings completed for the personal agent but not evaluated by the other agent.

    :param current_user: The username of the user, corresponding to the agent ID of the personal agent.
    :return: A dictionary containing the pairings incomplete for both personal agents.
    """
    client = await get_client(current_user)

    relations = await client.get_agent_sent_decisions()

    response = {'relations': relations}

    return response

@router.get("/get_agent_models")
async def get_agent_models(current_user: str = Depends(get_current_user)):
    """
    The method is called to get the available LLMs that can be used by the personal agent to evaluate the pairings, given the agent ID.

    :param current_user: The agent ID of the personal agent.
    :return: A dictionary mapping the LLM name to its status (active/inactive) depending on whether it is currently being used by the personal agent or not.
    """
    client = await get_client(current_user)

    models = await client.get_models()

    return {'models':     [{"name": name, "active": active} for name, active in models.items()]}

@router.post("/update_models")
async def pause_agent(data : dict, current_user: str = Depends(get_current_user)):
    """
    The method is called to update the available LLMs that can be used by the personal agent to evaluate the pairings, given the agent ID and a dictionary with the new models.

    :param data: A dictionary mapping the LLM name to its status (active/inactive).
    :param current_user: The agent ID of the personal agent.
    :return: A dictionary indicating that the models were updated successfully.
    """
    client = await get_client(current_user)

    operation_status = await client.update_models(data)

    return {"status": "model_updated"}


@router.post("/pause")
async def pause_agent(current_user: str = Depends(get_current_user)):
    """
    The method is called to pause the personal agent, given the agent ID.

    :param current_user: The agent ID of the personal agent.
    :return: A dictionary indicating that the personal agent was paused successfully.
    """
    client = await get_client(current_user)

    operation = await client.pause_user()

    if operation != Status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pause Operation failed"
        )

    return {"status": "pause_requested"}

@router.post("/resume")
async def resume_agent(current_user: str = Depends(get_current_user)):
    """
    A method is called to resume the personal agent, given the agent ID.

    :param current_user: The agent ID of the personal agent.
    :return: A dictionary indicating that the personal agent was resumed successfully.
    """
    client = await get_client(current_user)

    operation = await client.resume_user()

    if operation != Status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume Operation failed"
        )

    return {"status": "resume_requested"}

@router.post("/delete")
async def delete_agent(current_user: str = Depends(get_current_user)):
    """
    A method is called to delete the personal agent, given the agent ID.

    :param current_user: The agent ID of the personal agent.
    :return: A dictionary indicating that the personal agent was deleted successfully.
    """
    client = await get_client(current_user)

    operation = await client.delete_user()

    operation = await client.pause_user()

    if operation != Status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Delete Operation failed"
        )

    return {"status": "delete_requested"}

@router.post("/get_information")
async def get_information(information : dict, current_user: str = Depends(get_current_user)):
    """
    The method is called to get the information of a user, given the type of information to get (in the field 'type').

    :param information: A dictionary containing the type of information to get (in the field 'type').
    :param current_user: The username of the user requesting the information.
    :return: A dictionary containing the requested information.
    """
    information_type = RequestType(information['type'])
    client = await get_client(current_user)

    response = {}

    if information_type == RequestType.GET_PUBLIC_INFORMATION:
        response['public_information'] = await client.get_public_information()
    elif information_type == RequestType.GET_PRIVATE_INFORMATION:
        response['private_information'] = await client.get_private_information()
    elif information_type == RequestType.GET_POLICIES:
        response['policies'] = await client.get_policies()
    elif information_type == RequestType.GET_USER_INFORMATION:
        response = await client.get_information()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request type"
        )

    return response

@router.post("/feedback")
async def send_feedback(data : dict, current_user: str = Depends(get_current_user)):
    """
    The method is called to send feedback for a pairing, given the receiver and the feedback. (The user sending it is retrieved from the access token)

    :param data: A dictionary containing the receiver and the feedback for the pairing, in the fields 'receiver' and 'feedback', respectively.
    :param current_user: A string representing the username of the user sending the feedback.
    :return:
    """
    client = await get_client(current_user)

    await client.send_feedback(data['receiver'], data['feedback']==1)

    return {"status" : "feedback sent"}



app.include_router(router)


if __name__ == "__main__":
    """
    The main function is called to start the FastAPI application.
    """
    uvicorn.run(app, host="0.0.0.0", port=8000)

    # To handle encrypted communication:
    # uvicorn.run(app, ssl_keyfile="./key.pem", ssl_certfile="./cert.pem")