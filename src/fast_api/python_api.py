import os
from dataclasses import asdict

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
from pipenv.patched.safety.safety import fetch_database
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
from src.database import DATABASE_PATH, get_user, create_user, get_database, init_database

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
TOKEN_DURATION = timedelta(hours=1)

clients = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()

    # Initialize your resources and perform your startup tasks:
    model_name = "meta-llama/Llama-3.3-70B-Instruct"
    model_client_my_agent = get_model(
        model_type=ModelType.OLLAMA, model=model_name, temperature=0.7
    )
    model_client_orchestrator = get_model(
        model_type=ModelType.OLLAMA, model=model_name, temperature=0.5
    )

    try:
        # Start the runtime and register your agents
        Runtime.start_runtime()
        await register_my_agent(model_client_my_agent)
        await register_orchestrator(model_client_orchestrator)
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
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now() + TOKEN_DURATION
    to_encode.update({
        "exp": expire,
        "sub": str(data["sub"]),
        "type": "access"
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_client(username : str) -> Client | None:
    # To Do: load clients from database.
    async with lock:
        if username in clients:
            return clients[username]
        else:
            print("USER NOT FOUND!")
            return None

async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(payload)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    db = get_database()
    user = get_user(db, username)

    if not user:
        print(f"USER {username} NOT FOUND IN DB!")
        raise credentials_exception


    return username

@app.get("/")
async def read_root():
    return {"message": "Hello, world!"}

@router.post("/register")
async def register(registration_data_json : dict) -> dict:
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

    return {"status" : f"{registration_data_json['username']} is now registered."}


@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dict:
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
async def setup_user(setup_json: dict, user_token_data: str = Depends(get_current_user)):
    print("RHE")
    if setup_json["user"] != user_token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username",
        )

    print("HRE")

    client = await get_client(setup_json["user"])

    clients[setup_json["user"]] = client

    operation : Status = await client.setup_user(setup_json["content"])

    if operation != Status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setup failed"
        )

    return {"status": "setup_complete"}

@router.post("/change_information")
async def change_information(information_json: dict, user_token_data: str = Depends(get_current_user)):
    db = get_database()
    user = get_user(db, information_json["user"])

    if ("public_information" not in information_json.keys() or "private_information" not in information_json.keys()
            or "policies" not in information_json.keys()) or not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )

    if information_json["user"] != user_token_data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot setup another user"
        )

    client = Client(information_json["user"])

    operation : Status = await client.change_information(information_json["public_information"], information_json["private_information"], information_json["policies"])

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
async def get_relations(current_user: str = Depends(get_current_user)):
    client = await get_client(current_user)

    relations = await client.get_agent_established_relations()

    response = {'relations': relations}

    return response

@router.post("/pause")
async def pause_agent(current_user: str = Depends(get_current_user)):
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
    client = await get_client(current_user)

    operation = await client.resume_user()

    operation = await client.pause_user()

    if operation != Status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume Operation failed"
        )

    return {"status": "resume_requested"}

@router.post("/delete")
async def delete_agent(current_user: str = Depends(get_current_user)):
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
    client = await get_client(current_user)

    await client.send_feedback(data['receiver'], data['feedback'])

    return {"status" : "feedback sent"}



app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

    # To handle enrypted communication:
    # uvicorn.run(app, ssl_keyfile="./key.pem", ssl_certfile="./cert.pem")