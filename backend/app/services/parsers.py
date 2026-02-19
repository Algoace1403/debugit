import re


def classify_from_traceback(error_msg: str, traceback_str: str) -> tuple[str, str] | None:
    """
    Rule-based classification from Python/JS tracebacks.
    Returns (bug_type, fix_summary) or None if ambiguous (send to LLM).
    """
    # SYNTAX
    if "SyntaxError" in error_msg:
        if "expected ':'" in error_msg:
            return ("SYNTAX", "add the missing colon")
        if "unexpected EOF" in error_msg:
            return ("SYNTAX", "fix the unexpected end of file")
        return ("SYNTAX", "fix the syntax error")

    # INDENTATION
    if "IndentationError" in error_msg or "TabError" in error_msg:
        return ("INDENTATION", "correct indentation to 4 spaces")

    # IMPORT
    if "ImportError" in error_msg or "ModuleNotFoundError" in error_msg:
        module = re.search(r"No module named '(\w+)'", error_msg)
        if module:
            return ("IMPORT", f"add missing import for {module.group(1)}")
        return ("IMPORT", "fix the import statement")

    if "NameError" in error_msg:
        name = re.search(r"name '(\w+)' is not defined", error_msg)
        if name:
            return ("IMPORT", f"add missing import or definition for {name.group(1)}")

    # TYPE_ERROR
    if "TypeError" in error_msg:
        return ("TYPE_ERROR", "fix the type mismatch")

    # Ambiguous → send to Claude for LOGIC classification
    return None


def classify_from_linter(tool: str, message: str) -> tuple[str, str] | None:
    """Classify linter/type-checker output."""
    if tool in ("ruff", "flake8"):
        if re.match(r"F401", message):
            return ("LINTING", "remove the unused import")
        if re.match(r"F811", message):
            return ("LINTING", "remove the redefined name")
        if re.match(r"E1[0-9]{2}", message):
            return ("INDENTATION", "correct indentation")
        if re.match(r"E9[0-9]{2}", message):
            return ("SYNTAX", "fix the syntax error")
        return ("LINTING", "fix the linting issue")

    if tool in ("mypy", "pyright"):
        return ("TYPE_ERROR", "fix the type error")

    if tool == "tsc":
        return ("TYPE_ERROR", "fix the TypeScript type error")

    if tool == "eslint":
        if "no-unused-vars" in message:
            return ("LINTING", "remove the unused variable")
        return ("LINTING", "fix the linting issue")

    return None
