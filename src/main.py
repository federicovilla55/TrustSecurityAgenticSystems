import asyncio

import uvicorn
from jose import JWTError
from fastapi import FastAPI
from src import ModelType, Runtime, app
from src.runtime import Runtime, get_model, register_my_agent, register_orchestrator

async def run_setup():
    """
    The function is called to run the main application's backend using `uvicorn`, a python web framework
    used to handle api connections. The main is called to initialize FastAPI and allowing it to serve the actual request.

    :return: None
    """
    try:
        uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
    except (RuntimeError, JWTError) as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_setup())