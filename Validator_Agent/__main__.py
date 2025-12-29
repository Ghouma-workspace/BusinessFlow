import logging, click, uvicorn, os, sys

from constants import LOGGING_LEVEL

match LOGGING_LEVEL.lower():
    case "info":
        logging.basicConfig(level=logging.INFO)
    case "debug":
        logging.basicConfig(level=logging.DEBUG)
    case "error":
        logging.basicConfig(level=logging.ERROR)
    case _:
        logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

from Validator_Agent.validator_agent import root_agent as validator_agent
from logs.core.loggers import validator_logger as logger
from constants import APP_NAME


@click.command()
@click.option("--host", default="localhost")
@click.option("--port", default=8002)
def main(host, port):
    # Agent card (metadata)
    agent_card = AgentCard(
        name='Business Validator Agent',
        description=validator_agent.description,
        url=f'http://{host}:{port}',
        version="1.0.0",
        defaultInputModes=["text", "text/plain"],
        defaultOutputModes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="business_validator",
                name="Guide business idea to the best of your ability.",
                description="""
                Role:
                You are the validator of the entire business pipeline.
                You collect and extract the provided data and identify key values.
                You establish business rules and assymptions in parallel.
                You criticize and refine the business rules and idea and validate its coherence with the collected data.""",
                tags=["data", "rules", "validate"],
                examples=[
                    "Retrieve the data and perform a google search",
                    "Build business rules based on the provided idea",
                    "Validate the coherence of the collected data with the business rules"
                ],
            )
        ],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=ADKAgentExecutor(
            app_name=APP_NAME,
            agent=validator_agent,
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