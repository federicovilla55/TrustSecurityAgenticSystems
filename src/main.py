import asyncio

import uvicorn
from jose import JWTError

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