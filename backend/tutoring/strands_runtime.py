import math
import os

from dotenv import load_dotenv


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

MAX_MODEL_TOKENS = 8192
CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 60
MAX_RETRY_ATTEMPTS = 2


def create_bedrock_model(*, max_tokens: int, temperature: float):
    """Create a configured Strands BedrockModel only when explicitly requested."""
    region = os.getenv("AWS_REGION")
    model_id = os.getenv("BEDROCK_MODEL_ID")
    if not region or not model_id:
        raise RuntimeError(
            "Bedrock configuration error: AWS_REGION and BEDROCK_MODEL_ID are required."
        )
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int):
        raise ValueError("max_tokens must be a positive integer.")
    if not 0 < max_tokens <= MAX_MODEL_TOKENS:
        raise ValueError(f"max_tokens must be between 1 and {MAX_MODEL_TOKENS}.")
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
        raise ValueError("temperature must be a finite number between 0 and 1.")
    if not math.isfinite(float(temperature)) or not 0 <= float(temperature) <= 1:
        raise ValueError("temperature must be a finite number between 0 and 1.")

    import boto3
    from botocore.config import Config
    from strands.models import BedrockModel

    session_kwargs = {
        key: os.getenv(key)
        for key in ("aws_access_key_id", "aws_secret_access_key", "aws_session_token")
        if os.getenv(key)
    }
    session = boto3.Session(**session_kwargs, region_name=region)
    client_config = Config(
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        read_timeout=READ_TIMEOUT_SECONDS,
        retries={"max_attempts": MAX_RETRY_ATTEMPTS, "mode": "standard"},
    )
    return BedrockModel(
        boto_session=session,
        boto_client_config=client_config,
        model_id=model_id,
        max_tokens=max_tokens,
        temperature=float(temperature),
        streaming=False,
    )
