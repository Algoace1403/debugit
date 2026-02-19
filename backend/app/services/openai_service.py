from openai import AsyncOpenAI
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("openai_service")


def get_client() -> AsyncOpenAI:
    """Return an async OpenAI client."""
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def classify_bug(client: AsyncOpenAI, failure_info: dict, source_code: str) -> str:
    """Send a test failure to OpenAI for LOGIC classification. Returns raw text."""
    prompt = f"""Classify this test failure. It has already been ruled out as SYNTAX, INDENTATION, IMPORT, TYPE_ERROR, and LINTING.
Determine if this is a LOGIC error (wrong return value, incorrect condition, off-by-one, etc.).

Test file: {failure_info.get('test_file', '')}
Test name: {failure_info.get('test_name', '')}
Error message: {failure_info.get('error_message', '')}
Traceback: {failure_info.get('traceback', '')}

Source code of the file under test:
{source_code}

Respond with ONLY valid JSON (no markdown):
{{
  "bug_type": "LOGIC",
  "confidence": <0.0-1.0>,
  "root_cause": "<one sentence>",
  "affected_file": "<relative path>",
  "affected_line": <line number>,
  "fix_summary": "<short imperative sentence>"
}}"""

    logger.info("Calling OpenAI for bug classification...")
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    result = response.choices[0].message.content
    logger.info(f"OpenAI classification response: {result[:200]}")
    return result


async def generate_fix(client: AsyncOpenAI, classification: dict, file_content: str, error_info: str) -> str:
    """Ask OpenAI to generate a unified diff patch for a bug."""
    prompt = f"""Fix this {classification['bug_type']} bug.

File: {classification['file']}
Line: {classification['line']}
Root cause: {classification.get('root_cause', '')}
Error: {error_info}

Current file content (with line numbers):
{file_content}

Return ONLY a unified diff patch. Do NOT rewrite the whole file.
Limit changes to the minimum lines needed to fix this specific bug.
Do not add comments, do not refactor, do not change unrelated code.

Format:
--- a/{classification['file']}
+++ b/{classification['file']}
@@ ... @@
 context
-old line
+new line
 context"""

    logger.info(f"Calling OpenAI for fix generation: {classification['file']} ({classification['bug_type']})")
    response = await client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
    )
    result = response.choices[0].message.content
    logger.info(f"OpenAI fix response length: {len(result)} chars")
    return result
