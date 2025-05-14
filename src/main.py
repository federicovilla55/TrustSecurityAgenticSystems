import asyncio

import uvicorn
from jose import JWTError
from fastapi import FastAPI
from src import ModelType, Runtime, app
from src.runtime import Runtime, get_model, register_my_agent, register_orchestrator

async def run_setup():
    """
    The function to run the main application using uvicorn, a python web framework
    used to handle web connections from the browser or api client and allows
    allows FastAPI to serve the actual request.
    :return:
    """
    try:
        uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
    except (RuntimeError, JWTError) as e:
        print(f"FOUND ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(run_setup())