from google.adk.agents import SequentialAgent, LlmAgent
from google.adk.tools import google_search
from pydantic import BaseModel, Field
from typing_extensions import Literal, Union
from typing import List


class NavigateAction(BaseModel):
    """Represents an action to navigate to a specific URL."""

    action_type: Literal["navigate"] = "navigate"
    url: str = Field(description="The full URL to navigate to.")


class InteractAction(BaseModel):
    """Represents an action to interact with a web element."""

    action_type: Literal["interact"] = "interact"
    element_description: str = Field(
        description="A highly detailed description of the element to interact with."
    )
    interaction_type: Literal["click", "type", "select"] = Field(
        description="The type of interaction to perform."
    )
    value: str | None = Field(
        default=None, description="The text to type or the value to select."
    )


Action = Union[NavigateAction, InteractAction]


class Plan(BaseModel):
    """A structured plan of action for the web agent."""

    steps: List[Action] = Field(
        description="The list of sequential actions the agent must perform."
    )


# Agent 1: The Analyst - Finds and justifies URLs
url_suggestor = LlmAgent(
    name="UrlSuggestor",
    model="gemini-2.0-flash",
    description="Analyzes user requests and suggests the most relevant URLs.",
    tools=[google_search],
    instruction="""
    You are an expert web research analyst. Your job is to find the best starting URLs for a web automation task based on a user request.

    **Your Workflow:**
    1.  Analyze the user's request (e.g., "find academic papers on LLMs", "book a flight on Delta").
    2.  Use the `google_search` tool to find official and direct websites. Prioritize official sites (e.g., delta.com) over aggregators or articles.
    3.  Analyze the search results.
    4.  Output a short, ranked list of the top 1-3 URLs. For each URL, provide a brief justification for why it's a good choice.
    5.  Your output will be passed to a planning agent, so the justification is critical.

    **Example:**
    User Request: "I need to check my order status on Amazon"
    Your Final Output:
    1. https://www.amazon.com/gp/css/order-history - This is the direct URL for order history, which is the most efficient starting point.
    2. https://www.amazon.com - This is the homepage, a good fallback if the user needs to log in first.
    """,
    output_key="suggested_urls",
)

# Agent 2: The Strategist - Creates a detailed text-based plan
planning_generator_agent = LlmAgent(
    name="PlanningGeneratorAgent",
    model="gemini-2.0-flash",
    description="Breaks down user requests into detailed, actionable steps.",
    instruction="""
    You are a meticulous, expert web automation strategist. Your goal is to create a comprehensive, step-by-step plan.

    **Your Context:**
    - You will receive the original user request.
    - You will also receive a list of suggested URLs with justifications from a research analyst.

    **Your Task:**
    1.  Review the user request and the suggested URLs.
    2.  Choose the single best URL from the suggestions to start the task.
    3.  Create a detailed, step-by-step plan to achieve the user's goal.
    4.  Think about every single click and keystroke. Do not combine steps. A login requires typing a username, typing a password, and clicking a button (three separate steps).
    5.  Be extremely descriptive for `interact` steps. Instead of "search bar", say "the search input field with the placeholder text 'Search Wikipedia'".
    6.  The plan must be a numbered list starting with "Step 1:".
    7.  The only allowed actions are `navigate to [URL]` and `interact with [ELEMENT DESCRIPTION] to [ACTION]`.

    **Suggested URLs from Analyst:**
    {{suggested_urls}}

    Now, create the detailed, numbered plan.
    """,
    output_key="raw_steps",
)

# Agent 3: The Technician - Formats the plan into clean JSON
plan_formatter_agent = LlmAgent(
    name="PlanFormatter",
    model="gemini-2.0-flash",
    output_schema=Plan,
    instruction="""
    You are a data formatting expert. Your task is to convert the provided raw text,
    which contains a numbered list of steps, into a clean JSON object that conforms to the `Plan` schema.

    The raw text contains steps like "Step 1: navigate to https://..." or "Step 2: interact with...".
    You must parse each step and map it to the correct `NavigateAction` or `InteractAction` model.

    **Raw Text Input:**
    {{raw_steps}}

    Extract the steps and place them into a JSON list under the "steps" key.
    Your output MUST be a single, valid JSON object.
    """,
    output_key="plan",
)

planning_agent = SequentialAgent(
    name="planning_agent",
    description="Agent responsible for the full planning process from research to formatted plan.",
    sub_agents=[
        url_suggestor,
        planning_generator_agent,
        plan_formatter_agent,
    ],
)

__all__ = ["planning_agent", "Plan"]
