import click, uvicorn, os, sys

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

from Automation_Agent.automation_agent import root_agent as automation_agent
from logs.core.loggers import automation_logger as logger
from constants import APP_NAME


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""


@click.command()
@click.option("--host", default="localhost")
@click.option("--port", default=8003)
def main(host, port):
    # Agent card (metadata)
    agent_card = AgentCard(
        name='Email Automation Agent',
        description=automation_agent.description,
        url=f'http://{host}:{port}',
        version="1.0.0",
        defaultInputModes=["text", "text/plain"],
        defaultOutputModes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="email_automation",
                name="You are an email automation assistant.",
                description="You are designed to generate a report about the business workflow and send it to the user via email.",
                tags=["report", "email"],
                examples=[
                    "Generate a report",
                    "Send an email"
                ],
            )
        ],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=ADKAgentExecutor(
            app_name=APP_NAME,
            agent=automation_agent,
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
