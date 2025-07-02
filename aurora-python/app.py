import os
import time
import asyncio
import google.generativeai as genai
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

async def stream_gemini_response(message: str):
    chat = model.start_chat(history=[])
    response = chat.send_message(message, stream=True)
    for chunk in response:
        if text := chunk.text:
            yield text
            await asyncio.sleep(0.01)

@app.post("/api/chat")
async def chat_handler(request: ChatRequest):
    generator = stream_gemini_response(request.message)
    
    response_headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    }
    
    return StreamingResponse(generator, headers=response_headers)

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