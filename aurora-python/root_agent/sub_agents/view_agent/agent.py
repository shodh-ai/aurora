from google.adk.agents import Agent
from google.genai import types

view_agent = Agent(
    name="view_agent",
    model="gemini-2.5-flash",
    description="Analyzes images of web pages to describe their UI and content.",
    instruction="""You are a web page analyst.
    You will be provided with a base64 encoded image of a web page.
    Your task is to analyze its UI and content with extreme accuracy.
    Focus on key elements like buttons, search bars, input fields, and important text.
    You must be able to answer any question about the content shown in the image.
    The user will pass you a base64 encoded image string in the prompt. You must decode this string to analyze the image and answer the user's question.
    """,
)
