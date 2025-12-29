from logs.core.logging_config import configure_adk_logging, create_logger
from constants import LOGGING_LEVEL


validator_logger = create_logger(
    name="validator",
    filename="validator.log",
    level=LOGGING_LEVEL,
)

automation_logger = create_logger(
    name="automation",
    filename="automation.log",
    level=LOGGING_LEVEL,
)

policy_logger = create_logger(
    name="policy",
    filename="policy.log",
    level=LOGGING_LEVEL,
)

coordinator_logger = create_logger(
    name="coordinator",
    filename="coordinator.log",
    level=LOGGING_LEVEL,
)

workflow_log = create_logger(
    name="workflow",
    filename="workflow.log",
    level=LOGGING_LEVEL,
)
