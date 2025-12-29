import os

from google.adk.agents.llm_agent import Agent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from constants import WORKSPACE_DIR, PLATFORM, MODEL


if(os.getenv("GOOGLE_API_KEY") is None or os.getenv("GOOGLE_API_KEY") == ""):
    raise ValueError("Please provide `GOOGLE_API_KEY` in .env file")
else:
    model = f"{MODEL}"

toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params = StdioServerParameters(
            command='businessflow',
            args=["-u", "-m"],
            env={
                "WORKSPACE_DIR":WORKSPACE_DIR,
                "PLATFORM":PLATFORM,
            },
        ),
        timeout=15.0,
    ),
    tool_filter=['send_email']
)

root_agent = Agent(
    name="Email_Automation_Agent",
    model=model,
    description="An Automation Agent responsible for generating and emailing the final business report after approval.",
    instruction=f"""
    You are an Automation Agent responsible for executing the final approved action
    in the business automation workflow.

    You MUST strictly follow these rules:

    - You MUST execute your task ONLY if the QA Validator verdict is EXACTLY "APPROVED".
    - You MUST NOT modify, reinterpret, or critique any content.
    - You MUST NOT perform validation or business reasoning.
    - Your responsibility is strictly report generation and email delivery.

    All required inputs are automatically injected via the system state.

    **Task:**
    a) Verify that the QA Validator verdict is exactly "APPROVED".
        - If not, DO NOT perform any action.
    b) Generate a clear, professional business report using:
        - The executive summary
        - The validated business rules
        - The statistical summary
    c) Prepare an email with:
        - A concise and professional subject
        - A well-structured email body
    d) Send the email to the user using the tool `send_email`.

    Respond with ONLY a confirmation that the email has been successfully sent.
    """,
    tools=[toolset],
    output_key="automation_status"
)