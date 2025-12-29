import os, logging

logger = logging.getLogger(__name__)

from google.adk.agents.llm_agent import Agent
from google.adk.tools.tool_context import ToolContext
from google.adk.agents import LoopAgent, SequentialAgent, ParallelAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool
from Data_Agent.data_agent import root_agent as data_agent
from Business_Agent.business_agent import root_agent as business_agent
from constants import MODEL, RETRY_CONFIG


def exit_loop(tool_context: ToolContext):
  """Call this function ONLY when no further changes are needed, signaling the iterative process should end."""
  logger.info(f"  [Tool Call] exit_loop triggered by {tool_context.agent_name}")
  tool_context.actions.escalate = True
  # Return empty dict as tools should typically return JSON-serializable output
  return {}


if(os.getenv("GOOGLE_API_KEY") is None or os.getenv("GOOGLE_API_KEY") == ""):
    raise ValueError("Please provide `GOOGLE_API_KEY` in .env file")
else:
    model = f"{MODEL}"


aggregator_agent = Agent(
    name="AggregatorAgent",
    model=Gemini(model=model, retry_options=RETRY_CONFIG),
    instruction="""
    You MUST combine the FULL outputs of BOTH agents below.
    Do NOT proceed unless BOTH sections are present and complete.

    If either section is missing or incomplete, explicitly state that aggregation is NOT possible.

    **Collected Data Summary (MANDATORY)**
    {statistical_summary}

    **Business Logics and Rules (MANDATORY)**
    {business_specifications}

    Produce a single executive summary (~200 words) that PRESERVES:
    - Key statistics and numeric values
    - Explicit business rules and assumptions

    END OF EXECUTIVE SUMMARY
    """,
    output_key="executive_summary",
)


parallel_business_data_team = ParallelAgent(
    name="ParallelBusinessDataTeam",
    sub_agents=[data_agent, business_agent],
)


business_system_agent = SequentialAgent(
    name="BusinessSystem",
    sub_agents=[parallel_business_data_team, aggregator_agent],
)


validator_agent = Agent(
    name="QA_Validator",
    model=Gemini(model=model, retry_options=RETRY_CONFIG),
    description="A validation agent responsible for approving or rejecting business logic based on coherence with collected data.",
    instruction=f"""
    You are a QA Validator Agent acting as the final authority before automation.

    CRITICAL EXECUTION CONSTRAINTS:
    - You MUST base your evaluation ONLY on the provided executive summary.
    - You MUST NOT infer, assume, or invent missing data or business rules.
    - If the executive summary is incomplete, unclear, or missing required elements,
    you MUST treat this as NOT APPROVED and provide improvement suggestions.

    VALIDATION SEQUENCE (MANDATORY):
    1. Confirm that data-driven insights are present (numbers, KPIs, statistics).
    2. Confirm that business rules and assumptions are explicit.
    3. Confirm alignment between (1) and (2).

    DECISION RULES:
    - IF AND ONLY IF all three checks pass → respond EXACTLY with:
    APPROVED

    - OTHERWISE:
    - DO NOT mention data quality
    - DO NOT suggest collecting new data
    - Provide ONLY 2–3 actionable improvements on:
        • business rules
        • KPI definitions
        • assumptions
        • logic gaps

    You are evaluating the following EXECUTIVE SUMMARY ONLY:

    {{executive_summary}}
    """,
    output_key="qa_verdict"
)


refiner_agent = Agent(
    name="Business_Refiner",
    model=Gemini(model=model, retry_options=RETRY_CONFIG),
    description="A refinement agent responsible for improving business logic based on QA feedback.",
    instruction=f"""
    Your task is to analyze the QA Validator critique.

    IMPORTANT:
    - Your output REPLACES the previous business specifications.
    - This output WILL be re-evaluated by the QA Validator.
    - You MUST NOT exit the loop unless explicitly instructed via APPROVED.

    STRICT RULES:
    - IF the critique is EXACTLY "APPROVED":
        - You MUST call the function `exit_loop`
        - You MUST NOT generate any additional text

    - OTHERWISE:
        - Rewrite and improve the business rules and logic to fully address
        ALL points raised in the critique.
        - DO NOT modify, reference, or reinterpret the data.
        - DO NOT add new KPIs unless explicitly suggested by the critique.
        - Focus on clarity, feasibility, alignment, and logical consistency.

    QA Validator Critique:
    {{qa_verdict}}

    Current Business Specifications:
    {{business_specifications}}

    Produce ONLY the refined version of the business rules.
    """,
    output_key="business_specifications",
    tools=[FunctionTool(exit_loop)]
)


business_validator = LoopAgent(
    name="Business_Validator_Agent",
    sub_agents=[validator_agent, refiner_agent],
    max_iterations=3,
)


root_agent = SequentialAgent(
    name="BusinessPipeline",
    description="A Business Validation agent responsible for Validation-Controlled Execution",
    sub_agents=[business_system_agent, business_validator],
)