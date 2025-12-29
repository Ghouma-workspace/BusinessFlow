import json, os, uuid, httpx

from typing import Any

from a2a.client import A2ACardResolver
from a2a.types import (
    AgentCard,
    MessageSendParams,
    Part,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
)
from remote_agent_connection import (
    RemoteAgentConnections,
    TaskUpdateCallback,
)

from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.tool_context import ToolContext

from constants import VALIDATOR_AGENT_URL, EMIAL_AUTOMATION_AGENT_URL, MODEL, TIMEOUT
from logs.core.loggers import coordinator_logger as logger

root_agent = None
    

def convert_part(part: Part, tool_context: ToolContext):
    """Convert a part to text. Only text parts are supported."""
    if part.type == 'text':
        return part.text

    return f'Unknown type: {part.type}'


def convert_parts(parts: list[Part], tool_context: ToolContext):
    """Convert parts to text."""
    rval = []
    for p in parts:
        rval.append(convert_part(p, tool_context))
    return rval

def create_send_message_payload(
    text: str, task_id: str | None = None, context_id: str | None = None
) -> dict[str, Any]:
    """Helper function to create the payload for sending a task."""
    payload: dict[str, Any] = {
        'message': {
            'role': 'user',
            'parts': [{'type': 'text', 'text': text}],
            'messageId': uuid.uuid4().hex,
        },
    }

    if task_id:
        payload['message']['taskId'] = task_id

    if context_id:
        payload['message']['contextId'] = context_id
    return payload

class CoordinatorAgent:
    """The Coordinator agent. This is the agent responsible for sending tasks to agents.
    """

    def __init__(
        self,
        task_callback: TaskUpdateCallback | None = None,
    ):
        self.task_callback = task_callback
        self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        self.cards: dict[str, AgentCard] = {}
        self.agents: str = ''

    async def _async_init_components(
        self, remote_agent_addresses: list[str]
    ) -> None:
        """Asynchronous part of initialization."""
        # Use a single httpx.AsyncClient for all card resolutions for efficiency
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            for address in remote_agent_addresses:
                card_resolver = A2ACardResolver(
                    client, address
                )  # Constructor is sync
                try:
                    card = (
                        await card_resolver.get_agent_card()
                    )  # get_agent_card is async

                    remote_connection = RemoteAgentConnections(
                        agent_card=card, agent_url=address, logger=logger,
                    )
                    self.remote_agent_connections[card.name] = remote_connection
                    self.cards[card.name] = card
                except httpx.ConnectError as e:
                    logger.error(
                        f'ERROR: Failed to get agent card from {address}: {e}'
                    )
                except Exception as e:  # Catch other potential errors
                    logger.error(
                        f'ERROR: Failed to initialize connection for {address}: {e}'
                    )

        # Populate self.agents using the logic from original __init__ (via list_remote_agents)
        agent_info = []
        for agent_detail_dict in self.list_remote_agents():
            agent_info.append(json.dumps(agent_detail_dict))
        self.agents = '\n'.join(agent_info)

    @classmethod
    async def create(
        cls,
        remote_agent_addresses: list[str],
        task_callback: TaskUpdateCallback | None = None,
    ) -> 'CoordinatorAgent':
        """Create and asynchronously initialize an instance of the CoordinatorAgent."""
        instance = cls(task_callback)
        await instance._async_init_components(remote_agent_addresses)
        return instance

    def create_agent(self) -> Agent:
        """Create an instance of the CoordinatorAgent."""

        if(os.getenv("GOOGLE_API_KEY") is None or os.getenv("GOOGLE_API_KEY") == ""):
            raise ValueError("Please provide `GOOGLE_API_KEY` in .env file")
        else:
            model = f"{MODEL}"
        
        logger.info(f'Using hardcoded model: {model}')
        return Agent(
            model=model,
            name='Routing_agent',
            instruction=self.root_instruction,
            before_model_callback=self.before_model_callback,
            description=(
                'This coordinator agent plans the tasks and controls the workflow for the business automation'
            ),
            tools=[
                self.send_message,
            ],
        )

    def root_instruction(self, context: ReadonlyContext) -> str:
        """Generate the root instruction for the CoordinatorAgent."""
        current_agent = self.check_active_agent(context)
        return f"""
        **System Goal**
        The objective of this system is to help users **analyze, evaluate, and assess the likelihood of success of their business ideas**.
        This includes structured reasoning over user inputs and documents, validation of assumptions, consistency checks,
        and the generation of actionable insights and reports to support business decision-making.
        
        **Role:** You are the central coordination and orchestration agent. Your primary function is to understand the user's business idea, then plan, control, and supervise
        the end-to-end business automation workflow across multiple specialized agents.
        DO NOT perform data processing, business rule definition, validation, or automation actions yourself.
        Your responsibility is strictly orchestration, task delegation, and workflow control.
        Upon receiving a high-level business request from the user (along with documents directory and email address),
        you will perform the following tasks and then return the final validated outcome to the user:

        Task 1. **Workflow Planning**
        Task 2. **Parallel Task Execution and Validation & Control Loop**
        Task 4. **Automation Triggering**

        Before every task ask the user for approval to proceed and show the result of the previous task. 
        If any agent asks for clarifying question to the user relay it back to the user.

        You MUST operate as a state machine.

        You are NOT allowed to transition to the next task unless:
        1. The result of the current task has been presented to the user
        2. The user has explicitly approved proceeding

        Explicit approval is defined as one of:
        - "yes"
        - "approved"
        - "continue"
        - "proceed"

        If approval is missing or unclear:
        - STOP execution
        - Ask ONLY for approval
        - Do NOT call any agent

        For **Workflow Planning** task to be completed, confirm that:
        - The user request is fully understood
        - Required inputs are available (documents directory, email address)
        DO NOT PROCEED further until all missing inputs are provided.

        For **Validation-Controlled Execution**, you MUST:
        - Delegate the task to the Business Validator Agent
        - The Business Validator Agent is fully responsible for:
            - Transfer the data directory ONLY
            - Launching the Data Agent and Business Agent concurrently
            - Managing their parallel execution
            - Controlling the validation loop and critique cycle
            - Ensuring data outputs, KPIs, and statistics are consistent with business rules
        - You MUST NOT directly invoke or reference the Data Agent or Business Agent

        For **Automation Triggering**, ONLY proceed when validation is explicitly approved by the QA Validator Agent.
        This task consists solely of instructing the Automation Agent to generate the report and send it via email.

        **Core Directives:**
        * **Task Delegation:** Utilize the `send_message` function to assign each task to a remote agent.
        * **Contextual Awareness for Remote Agents:** If a remote agent repeatedly requests user confirmation, assume it lacks access to the full conversation history. In such cases, enrich the task description with all necessary contextual information relevant to that specific agent.
        * **Autonomous Agent Engagement:** Never seek user permission before engaging with remote agents. If multiple agents are required to fulfill a request, connect with them directly without requesting user preference or confirmation.
        * **Transparent Communication:** Always present the complete and detailed response from the remote agent to the user.
        * **User Confirmation Relay:** If a remote agent asks for confirmation, and the user has not already provided it, relay this confirmation request to the user.
        * **Focused Information Sharing:** Provide remote agents with only relevant contextual information. Avoid extraneous details.
        * **No Redundant Confirmations:** Do not ask remote agents for confirmation of information or actions.
        * **Tool Reliance:** Strictly rely on available tools to address user requests. Do not generate responses based on assumptions. If information is insufficient, request clarification from the user.
        * **Prioritize Recent Interaction:** Focus primarily on the most recent parts of the conversation when processing requests.
        * **Active Agent Prioritization:** If an active agent is already engaged, route subsequent related requests to that agent using the appropriate task update tool.

        **Agent Roster:**
        * Available Agents: `{self.agents}`
        * Currently Active Agent: `{current_agent['active_agent']}`
        """

    def check_active_agent(self, context: ReadonlyContext):
        state = context.state
        if (
            'session_id' in state
            and 'session_active' in state
            and state['session_active']
            and 'active_agent' in state
        ):
            return {'active_agent': f'{state["active_agent"]}'}
        return {'active_agent': 'None'}

    def before_model_callback(
        self, callback_context: CallbackContext, llm_request
    ):
        state = callback_context.state
        if 'session_active' not in state or not state['session_active']:
            if 'session_id' not in state:
                state['session_id'] = str(uuid.uuid4())
            state['session_active'] = True

    def list_remote_agents(self):
        """List the available remote agents you can use to delegate the task."""
        if not self.cards:
            return []

        remote_agent_info = []
        for card in self.cards.values():
            logger.info(f'Found agent card: {card.model_dump(exclude_none=True)}')
            logger.info('=' * 100)
            remote_agent_info.append(
                {'name': card.name, 'description': card.description}
            )
        return remote_agent_info

    async def send_message(
        self, agent_name: str, task: str, tool_context: ToolContext
    ):
        """Sends a task to remote agent.

        This will send a message to the remote agent named agent_name.

        Args:
            agent_name: The name of the agent to send the task to.
            task: The comprehensive conversation context summary
                and goal to be achieved regarding user inquiry.
            tool_context: The tool context this method runs in.

        Yields:
            A dictionary of JSON data.
        """
        if agent_name not in self.remote_agent_connections:
            raise ValueError(f'Agent {agent_name} not found')
        logger.info(f"sending message to {agent_name}")
        state = tool_context.state
        state['active_agent'] = agent_name
        client = self.remote_agent_connections[agent_name]

        if not client:
            raise ValueError(f'Client not available for {agent_name}')

        if 'context_id' in state:
            context_id = state['context_id']
        else:
            context_id = str(uuid.uuid4())

        message_id = ''
        metadata = {}
        if 'input_message_metadata' in state:
            metadata.update(**state['input_message_metadata'])
            if 'message_id' in state['input_message_metadata']:
                message_id = state['input_message_metadata']['message_id']
        if not message_id:
            message_id = str(uuid.uuid4())

        payload = {
            'message': {
                'role': 'user',
                'parts': [
                    {'type': 'text', 'text': task}
                ],
                'messageId': message_id,
            },
        }

        if context_id:
            payload['message']['contextId'] = context_id

        message_request = SendMessageRequest(
            id=message_id, params=MessageSendParams.model_validate(payload)
        )
        send_response: SendMessageResponse = await client.send_message(
            message_request=message_request
        )
        logger.info(f"send_response {send_response.model_dump_json(exclude_none=True, indent=2)}")

        if not isinstance(send_response.root, SendMessageSuccessResponse):
            logger.info('received non-success response. Aborting get task ')
            return None

        if not isinstance(send_response.root.result, Task):
            logger.info('received non-task response. Aborting get task ')
            return None

        return send_response.root.result


async def initialized_coordinator_agent() -> Agent:
    global root_agent
    if root_agent is None:
        coordinator_agent_instance = await CoordinatorAgent.create(
            remote_agent_addresses=[
                VALIDATOR_AGENT_URL,
                EMIAL_AUTOMATION_AGENT_URL
            ]
        )
        root_agent = coordinator_agent_instance.create_agent()

    return root_agent
