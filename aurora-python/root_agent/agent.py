import base64
import json
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.genai import types
from typing import Optional
import google.genai.errors

# Local imports from your project structure
from .sub_agents.interact_agent.agent import interact_agent
from .sub_agents.navigation_agent.agent import navigation_agent
from .sub_agents.view_agent.agent import view_agent
from .browser_manager import browser_manager

# NOTE: All custom retry logic (tenacity, google.api_core.retry) has been removed
# as it is not compatible with the Agent class constructor. We rely on the

# library's default retry behavior for server errors.


async def navigate_to_url(url: str) -> str:
    """Navigates the browser to the specified URL. Use this tool ONLY after you have extracted a URL from the navigation_agent tool."""
    if not url or not isinstance(url, str) or not url.startswith(('http://', 'https://')):
        return "Invalid or missing URL. You must provide a complete URL string, including http:// or https://."
    try:
        await browser_manager.navigate(url)
        return f"Navigation successful. The browser is now at {url}."
    except Exception as e:
        return f"An error occurred while navigating to {url}: {str(e)}"

async def execute_interaction(interaction_code: str) -> str:
    """Executes a Playwright script to interact with the current web page."""
    print(f"--- EXECUTING INTERACTION CODE ---")
    print(interaction_code)
    print("---------------------------------")
    return await browser_manager.execute_interaction(interaction_code)

async def get_elements_info_tool(selector: Optional[str] = None, limit: Optional[int] = None) -> str:
    """Returns information about interactive elements on the current page, optionally filtered by a Playwright selector.

    Args:
        selector (str, optional): A Playwright selector string (e.g., 'button', 'input[type="text"]', 'div.some-class'). If provided, only elements matching this selector will be returned. Defaults to None.
        limit (int, optional): The maximum number of elements to return. If provided, the function will return at most this many elements. Defaults to None.
    """
    return await browser_manager.get_elements_info(selector, limit)

async def get_latest_screenshot() -> str:
    """Gets the most recent screenshot taken by the browser manager. Returns the image as a base64 encoded string."""
    print(f"\n--- CALLING get_latest_screenshot ---")
    screenshot_bytes = browser_manager.last_sent_screenshot_bytes
    if not screenshot_bytes:
        result = "No screenshot available. Please ensure the browser view is active."
        print(f"Result: {result}")
        print("-------------------------------------")
        return result
    result = base64.b64encode(screenshot_bytes).decode("utf-8")
    print(f"Result: Screenshot data (base64 encoded) generated.")
    print("-------------------------------------")
    return result



# Update the description to be clear for the root agent's LLM
navigation_agent.description = "Use this agent to analyze a user's request to see if they want to go to a website. This agent will process the request and then return the specific URL to visit."
interact_agent.description = "Use this agent ONLY when the user wants to interact with the web page (e.g., click a button, fill a form, hover over an element). Pass the user's interaction request to this agent."

# ==============================================================================
# MODIFIED ROOT AGENT DEFINITION
# ==============================================================================
root_agent = Agent(
    name="root_agent",
    model="gemini-2.5-flash",
    description="A root agent that can browse the web and chat with the user.",
    instruction="""You are a helpful web browsing assistant. Your goal is to chat with the user, help the user by navigating a web browser, describing what is on the screen, and interacting with the page.

**Core Workflow:**
1.  **General Conversation:** For simple greetings or general conversation, respond conversationally. Do NOT use any tools unless the user's request explicitly asks for web browsing actions.

2.  **Navigation:** If the user requests to go to a website, ONLY follow these steps in order:
    - First, say "Searching for the website..."
    - Then, use the `navigation_agent` to get the URL.
    - Then, on a new line, say "Navigating to the website..."
    - Finally, use the `navigate_to_url` tool to open the URL.

3.  **Interaction:** If the user wants to interact with the page (e.g., "click the button", "fill the form", "scroll up/down", "hover over the text"), ONLY follow these steps in order:
    - First, say "Getting visual context of the page..."
    - Then, call `get_latest_screenshot` to get the latest screenshot.
    - Then, call `view_agent` with the screenshot to get visual context of the page.
    - Then, on a new line, say "Getting information about the elements on the page..."
    - Then, use the visual information and the user query to call `get_elements_info_tool(limit=10)` to get details about the relevant elements.
    - Then, on a new line, say "Executing interaction with the page..."
    - Then, pass the user's interaction request and the element information to the `interact_agent`. The `interact_agent` will generate the Playwright interaction code which will be sent to `execute_interaction` tool.
    - After the `interact_agent` has generated the code, ALWAYS immediately call `execute_interaction` with the code provided by `interact_agent` to perform the action on the web page.
    - Finally, briefly summarize the action taken for the user and conclude the interaction.

4.  **Answering Content Questions:** If the user asks a question about the *textual content* of the page (e.g., "what is the price of this item?", "what does this paragraph say?"), use the `get_elements_info_tool` tool to get the text content and use that to answer the question.

5.  **Answering Visual Questions:** ONLY if the user asks a question that *explicitly* requires visual analysis of the page (e.g., "where is the mic icon?", "what is in the top left corner?", "describe the layout"), first call `get_latest_screenshot` to get the screenshot, and then call `view_agent` with the screenshot to answer the user's query.
""",
    tools=[
        AgentTool(navigation_agent),
        navigate_to_url,
        AgentTool(interact_agent),
        execute_interaction,
        get_latest_screenshot,
        AgentTool(view_agent),
        get_elements_info_tool,
    ],
)