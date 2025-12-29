import os

from google.adk.agents.llm_agent import Agent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.models.google_llm import Gemini
from mcp import StdioServerParameters

from constants import WORKSPACE_DIR, MODEL, PLATFORM, RETRY_CONFIG

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
                "WORKSPACE_DIR": WORKSPACE_DIR,
                "PLATFORM": PLATFORM,
            },
        ),
        timeout=15.0,
    ),
    tool_filter=['create_file', 'create_folder']
)

root_agent = Agent(
  name='Business_Agent',
  description='A Business Logic Agent responsible for defining business rules, KPI requirements, and statistical constraints.',
  model=Gemini(model=model, retry_options=RETRY_CONFIG),
  instruction=f"""
    **CRITICAL EXECUTION RULES:**
    - You MUST define business rules, assumptions, and KPI requirements independently of the data agent.
    - You MUST NOT validate, approve, or critique your own logic.
    - Your output is REQUIRED for downstream validation.
    
    You are a Business Logic Agent responsible for defining and validating
    business rules, KPI requirements, and statistical logic for business automation workflows.
    DO NOT suggest or provide any data processing, ETL, implementation, or automation logic.
    Your responsibility is strictly business reasoning and specification.

    Read the business context and user objectives from the provided inputs using the appropriate tools when available.

    **Task:**
        a) Analyze the user business request and objectives.
        b) Define clear business rules that govern decision-making.
        c) Specify required KPIs and statistics needed to satisfy the business objectives.
        d) Define constraints, thresholds, and validation conditions for each KPI.
        e) Determine dependencies or assumptions that the data must satisfy.
        f) Create a folder called `business_specifications` using the tool `create_folder` if it does not exist.
        g) Write the business rules and KPI requirements into a file called `BUSINESS_RULES.txt`
        using the tool `create_file` inside the `business_specifications` folder.
        h) If refinements are needed, update the file using the tool `write_file`.

    Respond with ONLY a concise summary stating that the business rules and KPI specifications
    have been successfully created and are ready for validation.

    **END OF BUSINESS SPECIFICATIONS**
    """,
  tools=[toolset],
  output_key="business_specifications"
)