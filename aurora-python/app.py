import os
import asyncio
import google.generativeai as genai
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash-latest')
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
    return StreamingResponse(generator, media_type="text/plain")

@app.websocket("/ws/agent")
async def agent_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    async with async_playwright() as p:
        browser = await p.webkit.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.goto("https://www.google.com")

            while True:
                screenshot_bytes = await page.screenshot(type="jpeg", quality=70)
                
                await websocket.send_bytes(screenshot_bytes)
                
                await asyncio.sleep(0.5)

        except WebSocketDisconnect:
            print("Client disconnected.")
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            print("Closing browser...")
            await browser.close()

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