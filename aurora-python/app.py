from dotenv import load_dotenv

import asyncio
import base64
import json
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from browser_manager import browser_manager
from agents import root_agent

load_dotenv()
_original_default = json.JSONEncoder().default


def _new_default(obj):
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("utf-8")
    return _original_default(obj)


json.JSONEncoder.default = lambda self, obj: _new_default(obj)

if not os.getenv("GOOGLE_API_KEY"):
    raise ValueError(
        "GOOGLE_API_KEY not found in environment variables. Please ensure your .env file is correctly configured and located in the aurora-python directory."
    )

session_service = InMemorySessionService()
APP_NAME = "aurora"
client_sessions = {}

runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
)


class ChatRequest(BaseModel):
    message: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    browser_task = asyncio.create_task(browser_manager.start_browser())
    try:
        yield
    finally:
        await browser_manager.close_browser()
        browser_task.cancel()


app = FastAPI(lifespan=lifespan)


async def stream_agent_response(message: str, client_host: str):
    user_id = f"user_{client_host}"
    session_id = client_sessions.get(user_id)
    if not session_id:
        session_id = str(uuid.uuid4())
        client_sessions[user_id] = session_id
        session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
            state={"user_query": message},
        )
    else:
        session = session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        if session:
            session.state["user_query"] = message
            session_service.update_session(session)
    parts = [types.Part(text=message)]
    new_message_content = types.Content(role="user", parts=parts)

    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=new_message_content
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    yield part.text


@app.post("/api/chat")
async def chat_handler(request: ChatRequest, req: Request):
    client_host = req.client.host
    generator = stream_agent_response(request.message, client_host)
    return StreamingResponse(generator, media_type="text/plain")


@app.websocket("/ws/agent")
async def agent_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            screenshot_data = await browser_manager.get_screenshot()
            if screenshot_data and "screenshot" in screenshot_data:
                await websocket.send_bytes(screenshot_data["screenshot"])

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
