import logging
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from typing_extensions import override

from .execution_agent import execution_agent
from .planning_agent import (
    Plan,
    planning_agent,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RootAgent(BaseAgent):
    planning_agent: BaseAgent
    execution_agent: BaseAgent

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self, name: str, planning_agent: BaseAgent, execution_agent: BaseAgent, **kwargs
    ):
        super().__init__(
            name=name,
            planning_agent=planning_agent,
            execution_agent=execution_agent,
            sub_agents=[planning_agent, execution_agent],
            **kwargs,
        )

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # --- 1. Planning Phase (Runs Once) ---
        logger.info(
            f"[{self.name}] Running Planning Agent to generate the full plan..."
        )
        async for event in self.planning_agent.run_async(ctx):
            yield event

        plan_output = ctx.session.state.get("plan")

        if not plan_output or not isinstance(plan_output, dict):
            logger.error(
                f"[{self.name}] Planning agent did not produce a valid plan object. Aborting workflow."
            )
            return

        try:
            plan = Plan.model_validate(plan_output)
        except Exception as e:
            logger.error(
                f"[{self.name}] Failed to validate the plan structure: {e}. Aborting."
            )
            return

        if not plan.steps:
            logger.warning(
                f"[{self.name}] Planner generated an empty plan. Nothing to execute."
            )
            return

        logger.info(
            f"[{self.name}] Planning complete. Generated a plan with {len(plan.steps)} steps."
        )

        # --- 2. Execution Phase (Runs Sequentially) ---
        logger.info(f"[{self.name}] Starting execution of the plan...")
        for i, step in enumerate(plan.steps):
            current_step_number = i + 1
            ctx.session.state["current_step"] = step.model_dump()
            logger.info(
                f"[{self.name}] Executing Step {current_step_number}/{len(plan.steps)}: {step.action_type}"
            )

            async for event in self.execution_agent.run_async(ctx):
                yield event

            if not ctx.session.state.get("execution_succeeded"):
                error_message = ctx.session.state.get(
                    "execution_error", "Unknown execution failure."
                )
                logger.error(
                    f"[{self.name}] Step {current_step_number} failed: {error_message}. Halting workflow."
                )
                return

            logger.info(
                f"[{self.name}] Step {current_step_number} completed successfully."
            )

        logger.info(
            f"[{self.name}] Workflow finished successfully. All {len(plan.steps)} steps executed."
        )


root_agent = RootAgent(
    name="AuroraRootAgent",
    planning_agent=planning_agent,
    execution_agent=execution_agent,
)

__all__ = ["root_agent"]
