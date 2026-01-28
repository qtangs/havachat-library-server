import json
import os
import traceback

from dotenv import load_dotenv

load_dotenv(os.getenv("ENV_FILE"), override=True)

if env_secret := os.getenv("ENV_SECRET"):
    try:
        # Load environment variables from AWS Parameter Store
        print(
            f"Loading environment variables from {env_secret}\n"  # noqa: E501
        )

        # envs contains the environment variables in the format key=value
        import boto3

        ssm = boto3.client("ssm", region_name=os.getenv("REGION", "us-east-1"))
        response = ssm.get_parameter(Name=env_secret, WithDecryption=True)
        envs = response["Parameter"]["Value"]
        count = 0
        for line in envs.splitlines():
            if not line.strip() or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            os.environ[key] = value
            count += 1
            is_secret = (
                "KEY" in key.upper()
                or "TOKEN" in key.upper()
                or "SECRET" in key.upper()
                or "CRED" in key.upper()
            )
            print(
                f"    {key}{f'= {value}' if not is_secret else '=*****'}"  # noqa: E501
            )

        print(
            f"\nEnvironment variables loaded successfully. Total loaded: {count}"  # noqa: E501
        )
    except Exception as e:
        print(
            f"Error loading environment variables from AWS Parameter Store: {e}"  # noqa: E501
        )
        traceback.print_exc()

# General
PRODUCT = os.getenv("PRODUCT", "llm-app")
VERSION = os.environ.get("VERSION", "0")
ENV = os.getenv("ENV", "stg")
SG_TZ = "Asia/Singapore"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

AUTH_TOKEN_NAME = f"{PRODUCT}-{ENV}-auth-token"

os.environ["LANGCHAIN_PROJECT"] = os.getenv(
    "LANGCHAIN_PROJECT", f"{PRODUCT}-{ENV}"
)

BASE_PATH = os.path.dirname(os.path.realpath(__file__))

# Google Cloud
FIREBASE_ASSETS_STORAGE_BUCKET = os.getenv("FIREBASE_ASSETS_STORAGE_BUCKET")
FIREBASE_SERVICE_ACCOUNT_KEY_FILE = os.getenv(
    "FIREBASE_SERVICE_ACCOUNT_KEY_FILE"
)
FIREBASE_DOCS_COLLECTION_NAME = os.getenv(
    "FIREBASE_DOCS_COLLECTION_NAME", "docs"
)
FIREBASE_TRANSCRIPTS_COLLECTION_NAME = os.getenv(
    "FIREBASE_TRANSCRIPTS_COLLECTION_NAME", "transcripts"
)
FIREBASE_SUB_DOCS_COLLECTION_NAME = os.getenv(
    "FIREBASE_SUB_DOCS_COLLECTION_NAME", "sub_docs"
)
FIREBASE_ANALYTICS_COLLECTION_NAME = os.getenv(
    "FIREBASE_ANALYTICS_COLLECTION_NAME", "analytics"
)

# AWS
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "") or None
REGION = os.getenv("REGION", "us-east-1")

LLM_COST_LIMIT = json.loads(os.getenv("LLM_COST_LIMIT", "{}"))

DEFAULT_MODEL = "gpt-4o" if ENV in ["stg", "prd"] else "gpt-3.5-turbo"
DEFAULT_EMBEDDING_MODEL = os.getenv(
    "DEFAULT_EMBEDDING_MODEL", "openai/text-embedding-3-small"
)
