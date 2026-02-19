import anthropic
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("claude_service")


def get_client() -> anthropic.AsyncAnthropic:
    """Return an async Anthropic client."""
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def classify_bug(client: anthropic.AsyncAnthropic, failure_info: dict, source_code: str) -> str:
    """Send a test failure to Claude for LOGIC classification. Returns raw text."""
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

    logger.info(f"Calling Claude for bug classification...")
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    result = response.content[0].text
    logger.info(f"Claude classification response: {result[:200]}")
    return result


async def generate_fix(client: anthropic.AsyncAnthropic, classification: dict, file_content: str, error_info: str) -> str:
    """Ask Claude to generate a unified diff patch for a bug."""
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

    logger.info(f"Calling Claude for fix generation: {classification['file']} ({classification['bug_type']})")
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    result = response.content[0].text
    logger.info(f"Claude fix response length: {len(result)} chars")
    return result
