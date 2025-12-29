import asyncio
import os
import json
import subprocess
import sys
from pprint import pformat
import traceback
from typing import AsyncIterator

import gradio as gr
from google.genai import types
from google.adk.runners import Runner
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.adk.plugins.logging_plugin import LoggingPlugin

from constants import APP_NAME
from logs.core.loggers import workflow_log as logger


USER_ID = "default_user"
SESSION_ID = "default_session"

SESSION_SERVICE = InMemorySessionService()

COORDINATOR_AGENT_RUNNER: Runner | None = None
POLICY_ENFORCER_AGENT_RUNNER: Runner | None = None


async def read_file(path: str) -> str:
    if not path or not os.path.exists(path):
        return "File not found."
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"


def parse_policy_response(raw: str) -> tuple[str, str]:
    try:
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned)
        return data.get("decision", "safe"), data.get("reasoning", "")
    except Exception:
        logger.warning("Invalid policy JSON. Defaulting to SAFE.")
        return "safe", raw


# =============================
# Agent Initialization
# =============================

async def init_agents():
    logger.info(f"=================INITIALIZING COORDINATOR AGENT==============")
    try:
        logger.info(f"=================INITIALIZING Email Automation AGENT==============")
        with open("logs/automation.log", "w") as log_file:
            process = subprocess.Popen(
                [sys.executable, "-m", "Automation_Agent"],
                stdout=log_file,
                stderr=log_file,
                close_fds=True
            )
            ret = process.poll()  # or process.wait()
            if ret is not None and ret != 0:
                logger.error(f"Subprocess Automation_Agent exited with code {ret}")
    except Exception as e:
        logger.error(
            f"""
                STATUS: FAILURE TO START Email Automation AGENT
                ERROR: {str(e)}
                TRACEBACK:{traceback.format_exc()}
                PYTHON_EXECUTABLE: {sys.executable}
    """.strip()
        )
    await asyncio.sleep(5)
    
    try:
        logger.info(f"=================INITIALIZING Business Validation AGENT==============")
        with open("logs/validator.log", "w") as log_file:
            process = subprocess.Popen(
                [sys.executable, "-m", "Validator_Agent"],
                stdout=log_file,
                stderr=log_file,
                close_fds=True
            )
            ret = process.poll()  # or process.wait()
            if ret is not None and ret != 0:
                logger.error(f"Subprocess Validator_Agent exited with code {ret}")
    except Exception as e:
        logger.error(
            f"""
                STATUS: FAILURE TO START Business Validation AGENT
                ERROR: {str(e)}
                TRACEBACK:{traceback.format_exc()}
                PYTHON_EXECUTABLE: {sys.executable}
    """.strip()
        )
    await asyncio.sleep(5)

    logger.info(f"=================A2A Agents Intialized==============")
    await asyncio.sleep(5)
    
    from coordinator import initialized_coordinator_agent
    from Policy_Enforcer.policy_enforcement_agent import root_agent as policy_enforcement_agent
    global COORDINATOR_AGENT_RUNNER
    global POLICY_ENFORCER_AGENT_RUNNER

    coordinator_agent = await initialized_coordinator_agent()
    COORDINATOR_AGENT_RUNNER = Runner(
        agent=coordinator_agent,
        app_name=APP_NAME,
        session_service=SESSION_SERVICE,
        plugins=[LoggingPlugin()]
    )

    POLICY_ENFORCER_AGENT_RUNNER = Runner(
        agent=policy_enforcement_agent,
        app_name=APP_NAME,
        session_service=SESSION_SERVICE,
        plugins=[LoggingPlugin()]
    )

async def get_response_from_policy_agent(
    message: str,
    history: list[gr.ChatMessage],   
)-> AsyncIterator[gr.ChatMessage]:
    """Get response from policy agent."""
 
    policy_event_iterator: AsyncIterator[Event] = POLICY_ENFORCER_AGENT_RUNNER.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=types.Content(
            role='user', parts=[types.Part(text=message)]
        ),
    )

    async for event in policy_event_iterator:
        if event.is_final_response():
            final_response_text = ''
            if event.content and event.content.parts:
                final_response_text = ''.join(
                    [p.text for p in event.content.parts if p.text]
                )
            elif event.actions and event.actions.escalate:
                final_response_text = f"""
                {
                    "decision": "unsafe",
                    "reasoning": "Agent escalated: {event.error_message or "No specific message."}"
                }
                """
            if final_response_text:
                return final_response_text
        break


def get_policy_decision(policy_response_json:str):
    try:
        data = json.loads(policy_response_json.replace("```json", "").replace("```", "").strip())
        decision = ""
        reasoning = ""
        if "decision" in data:
            decision = data.get("decision")
            reasoning = data.get("reasoning")
        else:
            decision = "safe"
            reasoning = "safe"
    except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: for payload {policy_response_json}", e)
            decision = "safe"
            reasoning = policy_response_json
    return decision,reasoning



async def get_response_from_agent(
    message: str,
    history: list[gr.ChatMessage],
    model_name: str,
    api_key: str,
    timeout: str,
) -> AsyncIterator[gr.ChatMessage]:
    """Get response from host agent."""    
    if not model_name or model_name.strip() == "":
        yield gr.ChatMessage(role="assistant", content="❌ Please enter a Model Name.")
        return
    else:
        os.environ["MODEL"] = model_name.strip()
    
    if not api_key or api_key.strip() == "":
        yield gr.ChatMessage(role="assistant", content="❌ Please enter an API key.")
        return
    else:
        os.environ["GOOGLE_API_KEY"] = api_key
            
    if not timeout or timeout <= 0:
        yield gr.ChatMessage(role="assistant", content="❌ Please enter a Timeout.")
        return
    else:
        os.environ["TIMEOUT"] = str(timeout)

    try:
        if COORDINATOR_AGENT_RUNNER == None:
            await init_agents()
        
        policy_response_json = await get_response_from_policy_agent(message, history)
        decision,reasoning = get_policy_decision(policy_response_json)
        logger.info(f"Response from Policy Enforcer {decision} and reasoning is {reasoning}")
        if decision is not None and decision.lower() =="safe":
            event_iterator: AsyncIterator[Event] = COORDINATOR_AGENT_RUNNER.run_async(
                user_id=USER_ID,
                session_id=SESSION_ID,
                new_message=types.Content(
                    role='user', parts=[types.Part(text=message)]
                ),
            )
        else:
            yield gr.ChatMessage(
                role='assistant', content=reasoning
            )
            return

        async for event in event_iterator:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call:
                        formatted_call = f'```python\n{pformat(part.function_call.model_dump(exclude_none=True), indent=2, width=80)}\n```'
                        yield gr.ChatMessage(
                            role='assistant',
                            content=f'🛠️ **Tool Call: {part.function_call.name}**\n{formatted_call}',
                        )
                    elif part.function_response:
                        response_content = part.function_response.response
                        if (
                            isinstance(response_content, dict)
                            and 'response' in response_content
                        ):
                            formatted_response_data = response_content[
                                'response'
                            ]
                        else:
                            formatted_response_data = response_content
                        formatted_response = f'```json\n{pformat(formatted_response_data, indent=2, width=80)}\n```'
                        yield gr.ChatMessage(
                            role='assistant',
                            content=f'⚡ **Tool Response from {part.function_response.name}**\n{formatted_response}',
                        )
            if event.is_final_response():
                final_response_text = ''
                if event.content and event.content.parts:
                    final_response_text = ''.join(
                        [p.text for p in event.content.parts if p.text]
                    )
                elif event.actions and event.actions.escalate:
                    final_response_text = f'Agent escalated: {event.error_message or "No specific message."}'
                if final_response_text:
                    policy_response_json = await get_response_from_policy_agent(final_response_text,history)
                    decision,reasoning = get_policy_decision(policy_response_json)
                    logger.info(f"Response from Policy Enforcer {decision} and reasoning is {reasoning}")
                    if decision is not None and decision.lower() =="safe":
                        yield gr.ChatMessage(
                            role='assistant', content=final_response_text
                        )
                    else:
                        yield gr.ChatMessage(
                            role='assistant', content=reasoning
                        )
                break
    except Exception as e:
        logger.error(f'Error in get_response_from_agent (Type: {type(e)}): {e}')
        yield gr.ChatMessage(
            role='assistant',
            content='An error occurred while processing your request. Please check the server logs for details.',
        )


async def main():
    print('Creating ADK session...')
    await SESSION_SERVICE.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )
    print('ADK session created successfully.')

    with gr.Blocks(title="BUSINESSFLOW", fill_height=True) as demo:

        with gr.Row():
            gr.HTML("""
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div class="window-controls">
                        <span class="ctrl-close"></span>
                        <span class="ctrl-minimize"></span>
                        <span class="ctrl-maximize"></span>
                    </div>
                    <span style="font-family: 'Segoe UI', monospace; font-size: 20px; color: #E6E6E6; letter-spacing: 0.05em;">
                        🧑‍💻 BusinessFlow
                    </span>
                    <span style="color: #00D9FF; font-size: 20px; margin-left: 8px;">Guide Your Business</span>
                </div>
            """)
            gr.HTML("""
                <div style="display: flex; align-items: center; gap: 16px;">
                    <span style="color: #6272a4; font-size: 12px;">v0.0.1</span>
                </div>
            """)

        with gr.Row():
            with gr.Column(scale=1):
                model = gr.Textbox(label="LLM Model *",
                    type="text",
                    placeholder="Name of LLM Model",
                    show_label=True,
                )

                api_key = gr.Textbox(label="Provider API Key *",
                    type="password",
                    placeholder="sk-...",
                    show_label=True)
                
                timeout = gr.Slider(600, 1200, value=900, label="Timeout (s)")

                log_files = gr.FileExplorer(
                    root_dir="logs",
                    glob="*.log",
                    label="Logs",
                    height=150,
                )

                log_view = gr.Textbox(label="Log Content", lines=10)
                log_files.change(read_file, log_files, log_view)

            with gr.Column(scale=4):
                chat = gr.ChatInterface(
                    get_response_from_agent,
                    additional_inputs=[model, api_key, timeout],
                )
                chat.chatbot.height = 520

            with gr.Column(scale=2):
                files = gr.FileExplorer(root_dir="./workspace", label="Workspace")
                file_view = gr.Textbox(label="File Content", lines=12)
                files.change(read_file, files, file_view)

    print('Launching Gradio interface...')
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=8083,
        theme=gr.themes.Ocean(),
    )

    print('Gradio application has been shut down.')


if __name__ == "__main__":
    asyncio.run(main())
