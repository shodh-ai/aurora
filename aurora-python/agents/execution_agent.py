import logging
from typing import AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.tools import FunctionTool
from typing_extensions import override

from browser_manager import browser_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Tool Definitions ---
# All browser interactions are defined as tools for the LLM agents.

navigate_tool = FunctionTool(func=browser_manager.navigate)
click_element_tool = FunctionTool(func=browser_manager.click_element)
type_into_element_tool = FunctionTool(func=browser_manager.type_into_element)


# --- AGENT DEFINITIONS FOR 'NAVIGATE' ACTION ---

# A simple, direct agent to handle navigation.
navigate_worker = LlmAgent(
    name="NavigateWorker",
    model="gemini-2.0-flash",
    instruction="""
    You are a web navigation specialist.
    Extract the `url` from the `current_step` and call the `navigate` tool with that URL.

    **Current Step:**
    {{current_step}}
    """,
    tools=[navigate_tool],
)


# --- AGENT DEFINITIONS FOR 'CLICK' ACTION ---


class ClickableElementsFetcher(BaseAgent):
    """A BaseAgent to call the browser manager and fetch clickable elements."""

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        logger.info(f"[{self.name}] Fetching all clickable elements from the page...")
        elements_data = await browser_manager.get_clickable_elements()
        ctx.session.state["clickable_elements"] = elements_data.get(
            "clickable_elements", []
        )
        logger.info(
            f"[{self.name}] Found {len(ctx.session.state['clickable_elements'])} clickable elements."
        )
        if False:
            yield


click_decision_agent = LlmAgent(
    name="ClickDecisionAgent",
    model="gemini-2.0-flash",
    instruction="""
    You are a web interaction specialist. Your goal is to click an element.
    You have been given a command and a list of available elements from the webpage.

    **Command:**
    Click the element described as: "{{current_step.element_description}}"

    **Available Clickable Elements (JSON):**
    {{clickable_elements}}

    **Your Task:**
    1.  Analyze the list of elements.
    2.  Find the ONE element that is the best match for the command.
    3.  Call the `click_element` tool with the `id` of your chosen element.
    """,
    tools=[click_element_tool],
)

click_sequence_agent = SequentialAgent(
    name="ClickSequence",
    sub_agents=[
        ClickableElementsFetcher(name="ClickableElementsFetcher"),
        click_decision_agent,
    ],
)


# --- AGENT DEFINITIONS FOR 'TYPE' ACTION ---


class FormElementsFetcher(BaseAgent):
    """A BaseAgent to call the browser manager and fetch form elements."""

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        logger.info(f"[{self.name}] Fetching all form elements from the page...")
        elements_data = await browser_manager.get_form_elements()
        ctx.session.state["form_elements"] = elements_data.get("form_elements", [])
        logger.info(
            f"[{self.name}] Found {len(ctx.session.state['form_elements'])} form elements."
        )
        if False:
            yield


type_decision_agent = LlmAgent(
    name="TypeDecisionAgent",
    model="gemini-2.0-flash",
    instruction="""
    You are a data entry specialist. Your goal is to type text into a form field.
    You have been given a command and a list of available form elements.

    **Command:**
    In the element described as "{{current_step.element_description}}", type the value "{{current_step.value}}"

    **Available Form Elements (JSON):**
    {{form_elements}}

    **Your Task:**
    1.  Analyze the list of elements to find the best match for the command.
    2.  Call the `type_into_element` tool with the `id` of your chosen element and the `text` value from the command.
    """,
    tools=[type_into_element_tool],
)

type_sequence_agent = SequentialAgent(
    name="TypeSequence",
    sub_agents=[
        FormElementsFetcher(name="FormElementsFetcher"),
        type_decision_agent,
    ],
)


# --- The Top-Level ExecutionAgent ---
class ExecutionAgent(BaseAgent):
    """
    Dispatches a single step from a plan to the appropriate worker agent
    based on the step's action type.
    """

    navigate_worker: LlmAgent
    click_sequence: SequentialAgent
    type_sequence: SequentialAgent

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        name: str,
        navigate_worker: LlmAgent,
        click_sequence: SequentialAgent,
        type_sequence: SequentialAgent,
        **kwargs,
    ):
        super().__init__(
            name=name,
            navigate_worker=navigate_worker,
            click_sequence=click_sequence,
            type_sequence=type_sequence,
            sub_agents=[navigate_worker, click_sequence, type_sequence],
            **kwargs,
        )

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        ctx.session.state["execution_succeeded"] = False
        ctx.session.state["execution_error"] = None

        try:
            current_step = ctx.session.state.get("current_step")
            if not isinstance(current_step, dict):
                raise ValueError("No valid step found in session state.")

            action_type = current_step.get("action_type")
            logger.info(f"[{self.name}] Dispatching action: '{action_type}'")

            agent_to_run = None
            if action_type == "navigate":
                agent_to_run = self.navigate_worker
            elif action_type == "interact":
                interaction_type = current_step.get("interaction_type")
                if interaction_type == "click":
                    agent_to_run = self.click_sequence
                elif interaction_type == "type":
                    agent_to_run = self.type_sequence
                else:
                    raise ValueError(f"Unknown interaction type: '{interaction_type}'")
            else:
                raise ValueError(f"Unknown action type: '{action_type}'")

            tool_was_called = False
            async for event in agent_to_run.run_async(ctx):
                if event.get_function_calls():
                    tool_was_called = True
                    logger.info(
                        f"[{self.name}] Detected function_calls: {event.get_function_calls()}"
                    )
                if event.get_function_responses():
                    tool_was_called = True
                    logger.info(
                        f"[{self.name}] Detected function_responses: {event.get_function_responses()}"
                    )

                yield event

            if not tool_was_called:
                raise RuntimeError(
                    f"The agent '{agent_to_run.name}' completed without calling its required tool."
                )

            logger.info(f"[{self.name}] Successfully executed action: '{action_type}'")
            ctx.session.state["execution_succeeded"] = True

        except (ValueError, RuntimeError) as e:
            error_message = f"[{self.name}] Step execution failed: {e}"
            logger.error(error_message)
            ctx.session.state["execution_error"] = str(e)
        except Exception as e:
            error_message = f"[{self.name}] An unexpected error occurred: {e}"
            logger.exception(error_message)
            ctx.session.state["execution_error"] = (
                "An unexpected system error occurred."
            )


# --- Instantiation Block ---
execution_agent = ExecutionAgent(
    name="ExecutionAgent",
    navigate_worker=navigate_worker,
    click_sequence=click_sequence_agent,
    type_sequence=type_sequence_agent,
)
