from google.adk.agents import Agent
from google.genai import types

async def take_screenshot_tool() -> str:
    """Takes a screenshot of the current browser page."""
    # This is a placeholder and will be replaced by the actual implementation
    # in the root agent. The purpose is to make it available in the agent's tool list.
    return "Screenshot taken."

view_agent = Agent(
    name="view_agent",
    model="gemini-2.5-flash",
    description="Analyzes images of web pages to describe their UI and content.",
    instruction="""You are a web page analyst.
    You will be provided with an image of a web page.
    Your task is to analyze its UI and content with extreme accuracy.
    Focus on key elements like buttons, search bars, input fields, and important text.
    You must be able to answer any question about the content shown in the image.
    The user may pass you an image directly in the prompt. Analyze that image to answer the user's question.
    """,
)
