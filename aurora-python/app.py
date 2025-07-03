import os
import json
import asyncio
import google.generativeai as genai
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
from typing import Dict, Any, Optional, List

# Load environment variables and configure Google Generative AI
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Initialize models
root_model = genai.GenerativeModel('gemini-1.5-flash-latest')
navigation_model = genai.GenerativeModel('gemini-1.5-flash-latest')

app = FastAPI()

# Store active browser sessions
active_sessions = {}
current_url = "https://www.google.com"  # Default URL

class ChatRequest(BaseModel):
    message: str

# Navigation agent prompt template
NAVIGATION_AGENT_PROMPT = """
You are a website navigation agent. Your job is to analyze user requests and determine if they require visiting a specific website.
If the user wants to visit a website or perform actions on a specific site (like booking tickets, shopping, etc.), extract:
1. The website URL the user wants to visit
2. The specific action they want to perform (if any)

Output your response in this exact JSON format:
{
    "requires_navigation": true/false,
    "url": "full URL including https://",
    "action": "brief description of what the user wants to do",
    "explanation": "brief explanation of your decision"
}

If no website navigation is needed, set "requires_navigation" to false and leave "url" as an empty string.
Be specific with URLs - if the user mentions a specific website (like "bookmyshow"), provide the complete URL (like "https://in.bookmyshow.com").
"""

async def analyze_navigation_intent(message: str) -> Dict[str, Any]:
    """Use the navigation agent to extract navigation intent from user message"""
    try:
        navigation_chat = navigation_model.start_chat(history=[])
        response = await navigation_chat.send_message_async(
            f"{NAVIGATION_AGENT_PROMPT}\n\nUser request: {message}"
        )
        # Try to parse the response as JSON
        response_text = response.text
        # Find JSON content within the response if it exists
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx >= 0 and end_idx > start_idx:
            json_text = response_text[start_idx:end_idx]
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                print("Failed to parse JSON from navigation agent response")
                
        # Default response if JSON parsing fails
        return {
            "requires_navigation": False,
            "url": "",
            "action": "",
            "explanation": "Failed to parse navigation intent"
        }
    except Exception as e:
        print(f"Error in navigation intent analysis: {e}")
        return {
            "requires_navigation": False,
            "url": "",
            "action": "",
            "explanation": f"Error: {str(e)}"
        }

async def stream_root_agent_response(message: str, session_id: str):
    """Stream responses from the root agent with navigation capability"""
    chat = root_model.start_chat(history=[])
    
    # First, analyze navigation intent
    navigation_result = await analyze_navigation_intent(message)
    requires_navigation = navigation_result.get("requires_navigation", False)
    navigation_url = navigation_result.get("url", "")
    
    # If navigation is required, update the browser
    if requires_navigation and navigation_url:
        global current_url
        current_url = navigation_url
        # Update any active browser session
        if session_id in active_sessions:
            browser_page = active_sessions[session_id].get("page")
            if browser_page:
                try:
                    await browser_page.goto(navigation_url)
                    print(f"Navigated to: {navigation_url}")
                except Exception as e:
                    print(f"Navigation error: {e}")
    
    # Prepare a context-aware response for the root agent
    navigation_context = ""
    if requires_navigation:
        navigation_context = f"\n\nI've detected a website navigation intent and am directing the browser to {navigation_url}."
    
    # Generate the user-facing response
    root_prompt = f"""
    The user asked: "{message}"
    
    {navigation_context if requires_navigation else ""}
    
    Please respond to the user appropriately. If you're navigating to a website, let them know.
    """
    
    response = chat.send_message(root_prompt, stream=True)
    for chunk in response:
        if text := chunk.text:
            yield text
            await asyncio.sleep(0.01)

@app.post("/api/chat")
async def chat_handler(request: ChatRequest, req: Request):
    """Handle chat requests and potential navigation"""
    # Generate a session ID from the client's IP address if needed
    client_host = req.client.host
    session_id = f"session_{client_host}"
    
    generator = stream_root_agent_response(request.message, session_id)
    return StreamingResponse(generator, media_type="text/plain")

@app.websocket("/ws/agent")
async def agent_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = f"session_{websocket.client.host}"
    
    async with async_playwright() as p:
        browser = await p.webkit.launch(headless=True)
        page = await browser.new_page()
        
        # Store the page reference for navigation from chat responses
        active_sessions[session_id] = {
            "page": page,
            "browser": browser
        }
        
        try:
            # Navigate to the current global URL (may have been set by chat)
            await page.goto(current_url)
            
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
            if session_id in active_sessions:
                del active_sessions[session_id]
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