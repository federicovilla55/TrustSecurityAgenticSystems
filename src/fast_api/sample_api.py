import os
from dataclasses import asdict

from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
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
    PairingResponse, GetRequest, RequestType
)

SECRET_KEY = os.getenv("SECRET_KEY") if os.getenv("SECRET_KEY") else "secret"
ALGORITHM = "HS256"
TOKEN_DURATION = timedelta(hours=1)

app = FastAPI()
router = APIRouter(prefix="/api")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# To Do: Use a real database
database = {}

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

    return token_data.username

@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dict:
    user = database.get(form_data.username)
    if user is None or not (form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "access_token": create_access_token(data={"sub": user["username"]}),
        "token_type": "bearer"
    }

@router.post("/setup")
async def setup_user(setup_message: SetupMessage, user_token_data: TokenData = Depends(get_current_user)):
    if setup_message.user != user_token_data.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot setup another user"
        )

    # Send message to agent runtime
    await Runtime.send_message(
        message=setup_message,
        agent_type="my_agent",
    )
    return {"status": "setup_complete"}


@router.get("/relations")
async def get_relations(
    request: GetRequest,
    current_user: TokenData = Depends(get_current_user)
):
    if request.user != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot setup another user"
        )

    response = await Runtime.send_message(
        message=request,
        agent_type="orchestrator_agent"
    )
    return asdict(response)

@router.post("/pause")
async def pause_agent(current_user: TokenData = Depends(get_current_user)):
    await Runtime.send_message(
        message=GetRequest(
            request_type=RequestType.PAUSE_AGENT,
            user=current_user.username
        ),
        agent_type="orchestrator_agent"
    )
    return {"status": "pause_requested"}

@router.post("/resume")
async def resume_agent(current_user: TokenData = Depends(get_current_user)):
    await Runtime.send_message(
        message=GetRequest(
            request_type=RequestType.RESUME_AGENT,
            user=current_user.username
        ),
        agent_type="orchestrator_agent"
    )
    return {"status": "resume_requested"}

@router.post("/delete")
async def delete_agent(current_user: TokenData = Depends(get_current_user)):
    await Runtime.send_message(
        message=GetRequest(
            request_type=RequestType.DELETE_AGENT,
            user=current_user.username
        ),
        agent_type="orchestrator_agent"
    )
    return {"status": "delete_requested"}

app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)