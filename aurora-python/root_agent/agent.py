
import json
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from .sub_agents.navigation_agent.agent import navigation_agent
from .sub_agents.view_agent.agent import view_agent # Import the new view_agent
from .browser_manager import browser_manager

async def navigate_to_url(url: str) -> str:
    """Navigates the browser to the specified URL. Use this tool ONLY after you have extracted a URL from the navigation_agent tool."""
    if not url or not isinstance(url, str) or not url.startswith(('http://', 'https://')):
        return "Invalid or missing URL. You must provide a complete URL string, including http:// or https://."
    try:
        await browser_manager.navigate(url)
        return f"Navigation successful. The browser is now at {url}."
    except Exception as e:
        return f"An error occurred while navigating to {url}: {str(e)}"

import base64

async def get_current_screen_content() -> str:
    """Captures a screenshot of the current browser view and returns it as a base64 encoded string."""
    screenshot_bytes = await browser_manager.get_screenshot()
    if not screenshot_bytes:
        raise ValueError("Could not capture screenshot. Browser might not be active.")
    return base64.b64encode(screenshot_bytes).decode('utf-8')

async def get_page_text() -> str:
    """Returns the text content of the current page."""
    return await browser_manager.get_page_content_as_text()

# Update the description to be clear for the root agent's LLM
navigation_agent.description = "Use this agent to analyze a user's request to see if they want to go to a website. This agent will process the request and return the specific URL to visit."

root_agent = Agent(
    name="root_agent",
    model="gemini-1.5-flash-latest",
    description="A root agent that can browse the web and chat with the user.",
    instruction="""You are a helpful web browsing assistant. Your goal is to help the user by navigating a web browser and describing what is on the screen.

**Core Workflow:**
1.  **Navigation:** If the user requests to go to a website, use `navigation_agent` to get the URL, then `navigate_to_url` to open it.
2.  **Context Update:** After any navigation or significant browser interaction, and before responding to the user, **always** use the `get_current_screen_content` tool to get the current screen as a base64 encoded image. Then, pass the image to the `view_agent` to get a description of the screen.
3.  **Answering Content Questions:** If the user asks a question about the content of the page (e.g., "where is the account button?", "what is the price of this item?"), use the `get_page_text` tool to get the text of the page and use that to answer the question.
4.  **Answering Visual Questions:** If the user asks a question about the visual layout of the page (e.g., "where is the mic icon?", "what is in the top left corner?"), use the `get_current_screen_content` tool to get the current screen as a base64 encoded image. Then, pass the image to the `view_agent` to get a description of the screen.
5.  **Response:** Use the information from the `view_agent` and `get_page_text` to inform your responses, especially when describing the current page or answering questions about its content.
6.  **General Conversation:** For other queries, engage in normal conversation, but keep the current screen context in mind.
""""",
    tools=[
        AgentTool(navigation_agent),
        navigate_to_url,
        get_current_screen_content,
        AgentTool(view_agent),
        get_page_text,
    ],
)
