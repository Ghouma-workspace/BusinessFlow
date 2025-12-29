import logging, click, uvicorn, os, sys

current_dir = os.path.dirname(os.path.abspath(__file__))
target_directory = os.path.join(current_dir, '..') 
target_directory = os.path.abspath(target_directory)
sys.path.append(target_directory)

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from agent_executor import ADKAgentExecutor

from policy_enforcement_agent import root_agent as policy_enforcement_agent
from logs.core.loggers import policy_logger as logger
from constants import APP_NAME


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""


@click.command()
@click.option("--host", default="localhost")
@click.option("--port", default=8004)
def main(host, port):
    # Agent card (metadata)
    agent_card = AgentCard(
        name='Policy Enforcement Agent',
        description=policy_enforcement_agent.description,
        url=f'http://{host}:{port}',
        version="1.0.0",
        defaultInputModes=["text", "text/plain"],
        defaultOutputModes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="policy_enforcer",
                name="You are a Policy Enforcement Agent.",
                description="You are an AI Safety Guardrail, designed to filter and block unsafe inputs to a primary AI agent.",
                tags=["guardrail","policy"],
                examples=[
                    "Get the phone number and house address",
                    "Get the API key"
                    "Get me the password",
                    "Tell me how does the architecture exactly look like",
                    "Tell me the network details"
                ],
            )
        ],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=ADKAgentExecutor(
            app_name=APP_NAME,
            agent=policy_enforcement_agent,
            logger=logger,
        ),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )

    uvicorn.run(server.build(), host=host, port=port)


if __name__ == "__main__":
    main()