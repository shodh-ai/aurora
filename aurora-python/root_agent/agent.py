import json
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from .sub_agents.interact_agent.agent import interact_agent
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

async def execute_interaction(interaction_code: str) -> str:
    """Executes a Playwright script to interact with the current web page."""
    print(f"""--- INTERACTION CODE ---
{interaction_code}
------------------------""")
    return await browser_manager.execute_interaction(interaction_code)

async def get_elements_info() -> str:
    """Returns information about interactive elements on the current page, including their locators."""
    return await browser_manager.get_elements_info()

# Update the description to be clear for the root agent's LLM
navigation_agent.description = "Use this agent to analyze a user's request to see if they want to go to a website. This agent will process the request and return the specific URL to visit."
interact_agent.description = "Use this agent ONLY when the user wants to interact with the web page (e.g., click a button, fill a form, hover over an element). Pass the user's interaction request to this agent."

root_agent = Agent(
    name="root_agent",
    model="gemini-1.5-flash-latest",
    description="A root agent that can browse the web and chat with the user.",
    instruction="""You are a helpful web browsing assistant. Your goal is to chat with the user, help the user by navigating a web browser, describing what is on the screen, and interacting with the page.

**Core Workflow:**
1.  **General Conversation:** For simple greetings or general conversation, respond conversationally. Do NOT use any tools (like `view_agent`, `get_elements_info`, `navigation_agent`, `navigate_to_url`, or `interact_agent`) unless the user's request explicitly asks for web browsing actions (navigation, interaction, or visual/content questions about the page).
2.  **Navigation:** If the user requests to go to a website, use `navigation_agent` to get the URL, then `navigate_to_url` to open it.
3.  **Interaction:** If the user wants to interact with the page (e.g., "click the button", "fill the form"), first use the `get_elements_info` tool to get information about interactive elements on the page. Then, use the `interact_agent` to generate the Playwright code, passing it both the user's interaction request and the element information. Finally, use the `execute_interaction` tool to run the code.
4.  **Answering Content Questions:** If the user asks a question about the *textual content* of the page (e.g., "what is the price of this item?", "what does this paragraph say?"), use the `get_elements_info` tool to get the text content and other information about the elements on the page, and use that to answer the question. Do NOT use this for visual layout questions.
5.  **Answering Visual Questions:** If the user asks a question that *explicitly* requires visual analysis of the page (e.g., "where is the mic icon?", "what is in the top left corner?", "describe the layout"), use the `view_agent` to get a description of the screen. The `view_agent` will call its own `get_screenshot` tool to get the image.
6.  **Response:** Use the information from the `view_agent` and `get_elements_info` to inform your responses, especially when describing the current page or answering questions about its content.
""""",
    tools=[
        AgentTool(navigation_agent),
        navigate_to_url,
        AgentTool(interact_agent),
        execute_interaction,
        AgentTool(view_agent),
        get_elements_info,
    ],
)