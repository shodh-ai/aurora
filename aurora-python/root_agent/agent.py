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

async def get_elements_info_tool(selector: Optional[str] = None) -> str:
    """Returns information about interactive elements on the current page, optionally filtered by a Playwright selector.

    Args:
        selector (str, optional): A Playwright selector string (e.g., 'button', 'input[type="text"]', 'div.some-class'). If provided, only elements matching this selector will be returned. Defaults to None.
    """
    return await browser_manager.get_elements_info(selector)

async def get_view_of_page(query: Optional[str] = None) -> str:
    """Gets a description of the current view of the page by taking a screenshot and asking the view_agent to analyze it."""
    # Retrieve the last screenshot that was sent to the frontend
    screenshot_bytes = browser_manager.last_sent_screenshot_bytes
    if not screenshot_bytes:
        return "No screenshot available. Please ensure the browser view is active."

    image_part = types.Part(
        inline_data=types.Blob(mime_type="image/jpeg", data=screenshot_bytes)
    )

    # Prepare the prompt for the view_agent's underlying model
    prompt_parts = [image_part]
    if query:
        prompt_parts.append(types.Part(text=query))
    else:
        # Provide a default, detailed query if none is specified
        prompt_parts.append(types.Part(text="Describe the webpage in the image in detail. What is the main purpose of the page? What interactive elements like buttons, links, or forms are visible?"))

    # The view_agent is an LLMAgent. We can access its underlying LLM to make a direct call,
    # bypassing the full agent lifecycle, which avoids the run_async TypeError.
    # This is a targeted way to use the view_agent's configured model and instructions for a specific task.
    if not hasattr(view_agent, "_llm"):
        return "Error: view_agent is not configured with a compatible LLM."

    try:
        # We manually construct the contents list, including the agent's instructions as a system prompt.
        contents = [
            types.Content(role="system", parts=[types.Part(text=view_agent.instruction)]),
            types.Content(role="user", parts=prompt_parts)
        ]
        
        # Use the agent's internal LLM wrapper to generate the content.
        response = await view_agent._llm.generate_async(prompt=contents)
        
        # Extract and return the text from the response.
        return "".join(part.text for part in response[0].parts if hasattr(part, "text"))
    except Exception as e:
        print(f"An error occurred while calling the view_agent's LLM: {e}")
        return "Failed to get a description from the view agent."

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
1.  **General Conversation:** For simple greetings or general conversation, respond conversationally. Do NOT use any tools (like `view_agent`, `get_elements_info_tool`, `navigation_agent`, `navigate_to_url`, or `interact_agent`) unless the user's request explicitly asks for web browsing actions.

2.  **Navigation:** If the user requests to go to a website, follow these steps in order:
    - First, say "Searching for the website..."
    - Then, use the `navigation_agent` to get the URL.
    - Then, on a new line, say "Navigating to the website..."
    - Finally, use the `navigate_to_url` tool to open the URL.

3.  **Interaction:** If the user wants to interact with the page (e.g., "click the button", "fill the form"), follow these steps in order:
    - First, say "Getting visual context of the page..."
    - Then, call `view_agent` to get a description of the screen.
    - Then, on a new line, say "Getting information about the elements on the page..."
    - Then, use the visual information to call `get_elements_info_tool()` to get details about the relevant elements.
    - Then, on a new line, say "Executing interaction with the page..."
    - Then, pass the element information to the `interact_agent` to generate the interaction code.
    - Finally, use the `execute_interaction` tool to run the code.

4.  **Answering Content Questions:** If the user asks a question about the *textual content* of the page (e.g., "what is the price of this item?", "what does this paragraph say?"), use the `get_elements_info_tool` tool to get the text content and use that to answer the question.

5.  **Answering Visual Questions:** If the user asks a question that *explicitly* requires visual analysis of the page (e.g., "where is the mic icon?", "what is in the top left corner?", "describe the layout"), use the `view_agent` to get a description of the screen to answer the user's query.
""",
    tools=[
        AgentTool(navigation_agent),
        navigate_to_url,
        AgentTool(interact_agent),
        execute_interaction,
        AgentTool(view_agent),
        get_elements_info_tool,
    ],
)