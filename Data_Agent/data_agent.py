import os

from google.adk.tools import google_search
from google.adk.agents.llm_agent import Agent
from google.adk.agents import SequentialAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.models.google_llm import Gemini
from constants import RETRY_CONFIG, WORKSPACE_DIR, PLATFORM, MODEL
from mcp import StdioServerParameters


if(os.getenv("GOOGLE_API_KEY") is None or os.getenv("GOOGLE_API_KEY") == ""):
    raise ValueError("Please provide `GOOGLE_API_KEY` in .env file")
else:
    model = f"{MODEL}"

rag_agent_toolset = McpToolset(
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
    tool_filter=['rag_retrieve']
)

summary_agent_agent_toolset = McpToolset(
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


rag_agent = Agent(
  name='RAG_Data_Collector',
  description='A Retrieval Agent responsible for collecting ranked numerical and factual data using a specialized RAG tool.',
  model=Gemini(model=model, retry_options=RETRY_CONFIG),
  instruction=f"""
    **CRITICAL EXECUTION RULES:**
    - You MUST fully complete your task before any validation can occur.
    - You MUST produce quantitative outputs including raw values, statistics, and KPI-ready measures.
    - Your output is REQUIRED and will be consumed by downstream agents.
    - You MUST NOT perform validation or approval decisions.
    
    You are a Data Retrieval Agent responsible for collecting
    numerical and factual information relevant to KPI and statistical analysis.
    DO NOT clean, transform, summarize, or interpret the data.
    Your responsibility is strictly retrieval and ranking.

    State injection between agents is handled automatically.
    DO NOT persist outputs to files.

    **Task:**
        a) Use the tool `rag_retrieve` to retrieve and rank relevant documents from the user-provided documents directory.
            You MUST provide the following arguments when calling the tool:
            - documents_path: the path to the user-provided documents directory
            - query: a concise natural language query derived from the user request
        b) Ensure document content is truncated and ranked using top-k selection.
        c) Perform an external web search using the tool `google_search` to collect numerical or statistical information.
        d) Aggregate retrieved document data and web search results into
        a structured output suitable for downstream processing.
        e) Return ONLY raw retrieved content with source attribution.

    Respond with ONLY a confirmation that data retrieval has been completed
    and that the retrieved data is ready for formatting and cleaning.

    **END OF DATA ANALYSIS**
    """,
  tools=[rag_agent_toolset, google_search],
  output_key="retrieved_raw_data"
)


etl_agent = Agent(
  name='Data_Formatter_Cleaner',
  description='An ETL Agent responsible for cleaning, transforming, and identifying relevant numerical and statistical data.',
  model=Gemini(model=model, retry_options=RETRY_CONFIG),
  instruction=f"""You are a Data Formatting and Cleaning Agent responsible for transforming
    retrieved raw data into structured, consistent, and analyzable datasets.
    DO NOT summarize or apply business logic.
    Your responsibility is strictly ETL and data preparation.

    Input data : {{retrieved_raw_data}}
    DO NOT read from or write to files.

    **Task:**
        a) Consume the retrieved raw data from the injected state.
        b) Normalize numerical values, units, and formats.
        c) Correct inconsistencies and resolve missing numerical data when possible.
        d) Remove irrelevant or non-numerical information.
        e) Identify and isolate the most relevant numerical values and statistical measures.
        f) Structure the cleaned data in a format suitable for statistical summarization.

    Respond with ONLY a confirmation that data formatting and cleaning is completed
    and that the processed data is ready for statistical summarization.
    """,
  tools=[],
  output_key="processed_structured_data"
)


summary_agent = Agent(
  name='Statistical_Summarizer',
  description='A Summarization Agent responsible for extracting numerical values and statistical measurements for KPI readiness.',
  model=Gemini(model=model, retry_options=RETRY_CONFIG),
  instruction=f"""You are a Statistical Summarization Agent responsible for producing
    concise summaries focused strictly on numerical values, metrics, and statistical measurements.
    DO NOT define KPIs or apply business rules.
    Your responsibility is strictly numerical summarization.

    Input data : {{processed_structured_data}}.
    DO NOT read from or write to files.

    **Task:**
        a) Consume the processed structured data from the injected state.
        b) Identify key numerical values, distributions, and statistical measures.
        c) Extract raw values, totals, averages, variances, trends, and ranges when present.
        d) Focus on data elements most relevant for KPI computation.
        e) Identify and isolate the most relevant numerical values and statistical measures.
        f) Create a folder called `data` using the tool `create_folder` if it does not exist.
        g) Write the results about the identified values and computed numerical values as `DATA.txt` using the tool `create_file`.

    Respond with ONLY a confirmation that the statistical summary is completed
    and ready for validation by the QA Validator Agent.
    """,
  tools=[summary_agent_agent_toolset],
  output_key="statistical_summary"
)


root_agent = SequentialAgent(
    name="Data_Agent",
    sub_agents=[rag_agent, etl_agent, summary_agent],
    description="Retrieves data from provided documents and perform a web search, cleans and formats it then extracts the key values."
)