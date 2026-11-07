"""Send one test prompt to Gemini using the key in the local .env file.

The API key is never hardcoded and is never printed. Set GEMINI_MODEL in
.env to choose a different model. The default is a current free-tier model.

Run from the project folder:

    python src/test_gemini.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

try:
    from google import genai
    from google.genai import errors
except ImportError:
    print(
        "Error: the google-genai package is not installed. "
        "Install project dependencies with: pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)


# Free-tier text model recommended for new Gemini API projects.
# Override it by setting GEMINI_MODEL in the environment or in .env.
DEFAULT_MODEL = "gemini-3.5-flash-lite"

TEST_PROMPT = (
    "Explain in one sentence why a first-time mutual fund investor "
    "might discontinue a SIP."
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


def redact_secret(message: str, secret: str) -> str:
    """Remove the API key from any text before it is shown."""
    if secret and secret in message:
        return message.replace(secret, "[redacted]")
    return message


def load_settings() -> tuple[str, str]:
    """Read the API key and optional model name from the local .env file."""
    load_dotenv(ENV_PATH)

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print(
            "Error: GEMINI_API_KEY is missing. Add it to the .env file in the "
            "project folder, for example: GEMINI_API_KEY=your_key_here",
            file=sys.stderr,
        )
        sys.exit(1)

    model = os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_MODEL
    return api_key, model


def main() -> None:
    """Call Gemini with the test prompt and print only the reply."""
    api_key, model = load_settings()
    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(model=model, contents=TEST_PROMPT)
    except errors.APIError as exc:
        status = getattr(exc, "code", "unknown")
        detail = redact_secret(str(getattr(exc, "message", "") or exc), api_key)
        print(
            f"Error: the Gemini API request failed (status {status}). {detail}",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as exc:
        detail = redact_secret(str(exc), api_key)
        print(f"Error: the Gemini request could not be completed. {detail}", file=sys.stderr)
        sys.exit(1)

    reply = getattr(response, "text", None)
    if not reply or not str(reply).strip():
        print(
            "Error: Gemini returned no text. Check GEMINI_MODEL and try again.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(str(reply).strip())


if __name__ == "__main__":
    main()
