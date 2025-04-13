import asyncio
import os
from typing import Optional

import uvicorn
from fastapi import FastAPI
from jose import JWTError

from src import ModelType, Runtime, app
from src.runtime import Runtime, get_model, register_my_agent, register_orchestrator
#from .fast_api.python_api import app

async def run_setup():
    try:
        uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
    except (RuntimeError, JWTError) as e:
        print(f"FOUND ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(run_setup())