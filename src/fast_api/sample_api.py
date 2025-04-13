import os
from dataclasses import asdict

from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from uuid import UUID, uuid4
import logging
import asyncio
import uvicorn

from src import (
    Runtime, SetupMessage, ConfigurationMessage, PairingRequest,
    PairingResponse, GetRequest, RequestType, Client, Status
)

SECRET_KEY = os.getenv("SECRET_KEY") if os.getenv("SECRET_KEY") else "secret"
ALGORITHM = "HS256"
TOKEN_DURATION = timedelta(hours=1)

app = FastAPI()
router = APIRouter(prefix="/api")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# To Do: Use a real database
database = {}

lock = asyncio.Lock()

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now() + TOKEN_DURATION
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_client(username : str) -> Client:
    return database[username]['client']

async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
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
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    if username not in database:
        raise credentials_exception

    return username

@router.post("/register")
async def register(registration_data_json : dict) -> dict:
    async with lock:
        if registration_data_json["username"] in database:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Username already registered",
            )


        database[registration_data_json["username"]] = {
            "username": registration_data_json["username"],
            "hashed_password": pwd_context.hash(registration_data_json["password"]),
        }

    return {"status" : f"{registration_data_json['username']} is now registered."}


@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dict:
    user = database.get(form_data.username)
    if user is None or not pwd_context.verify(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "access_token": create_access_token(data={"sub": user["username"]}),
        "token_type": "bearer"
    }

@router.post("/setup")
async def setup_user(setup_json: dict, user_token_data: str = Depends(get_current_user)):

    if setup_json["user"] not in database:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )

    if setup_json["user"] != user_token_data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot setup another user"
        )

    client = Client(setup_json["user"])

    database[setup_json["user"]]['client'] = client

    operation : Status = await client.setup_user(setup_json["content"])

    if operation != Status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setup failed"
        )

    return {"status": "setup_complete"}



@router.post("/change_information")
async def change_information(information_json: dict, user_token_data: str = Depends(get_current_user)):
    if information_json["user"] not in database or "public_information" not in information_json.keys() \
            or "private_information" not in information_json.keys() or "policies" not in information_json.keys():
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

    return {"status": "Information updated."}

@router.get("/relations")
async def get_relations(current_user: str = Depends(get_current_user)):
    client = get_client(current_user)

    relations = await client.get_agent_established_relations()

    response = {'relations': relations}

    return response

@router.post("/pause")
async def pause_agent(current_user: str = Depends(get_current_user)):
    client = get_client(current_user)

    operation = await client.pause_user()

    if operation != Status.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pause Operation failed"
        )

    return {"status": "pause_requested"}

@router.post("/resume")
async def resume_agent(current_user: str = Depends(get_current_user)):
    client = get_client(current_user)

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
    client = get_client(current_user)

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
    client = get_client(current_user)

    response = {}

    if information_type == RequestType.GET_PUBLIC_INFORMATION:
        response['public_information'] = await client.get_public_information()
    elif information_type == RequestType.GET_PRIVATE_INFORMATION:
        response['private_information'] = await client.get_private_information()
    elif information_type == RequestType.GET_POLICIES:
        response['policies'] = await client.get_policies()
    elif information_type == RequestType.GET_USER_INFORMATION:
        ...
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request type"
        )

    return response

app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

    # To handle enrypted communication:
    # uvicorn.run(app, ssl_keyfile="./key.pem", ssl_certfile="./cert.pem")