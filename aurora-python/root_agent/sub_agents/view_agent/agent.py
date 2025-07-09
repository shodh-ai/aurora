from google.adk.agents import Agent

view_agent = Agent(
    name="view_agent",
    model="gemini-1.5-flash-latest",
    description="Analyzes images and describes their content.",
    instruction="""You are provided with an image of a web page. Your task is to analyze its UI and content with extreme accuracy. 
Focus on key elements like buttons, search bars, and icons. 
You must be able to answer any question about the content shown in the image.""",
)