"""
Rule-based fix generator — fallback when Claude is unavailable.

Generates unified diffs for common bug patterns:
- LINTING: Remove unused imports, trailing whitespace
- SYNTAX: Add missing colon
- INDENTATION: Fix to 4-space indentation
- IMPORT: Remove unused import / fix NameError typos
- LOGIC: Detect simple arithmetic operator swaps (+/-, *//), zero-division guards
- TYPE_ERROR: Add int()/str() cast if obvious

Each function returns a unified diff string or "" if it can't fix.
"""
import re
import os
from app.utils.logger import get_logger

logger = get_logger("rule_fixer")


def generate_rule_based_fix(
    repo_path: str,
    classification: dict,
    failure: dict | None = None,
) -> str:
    """
    Try to generate a unified diff for the classified bug using rules.

    Returns:
        Unified diff string, or "" if rule-based fix is not possible.
    """
    bug_type = classification.get("bug_type", "")
    file_rel = classification.get("file", "")
    line_num = classification.get("line", 0)
    root_cause = classification.get("root_cause", "")
    error_msg = (failure or {}).get("error_message", "")
    traceback_str = (failure or {}).get("traceback", "")

    if not file_rel or file_rel == "unknown":
        logger.info("RULE_FIXER: No file specified, cannot generate fix")
        return ""

    full_path = os.path.join(repo_path, file_rel)
    try:
        with open(full_path) as f:
            lines = f.readlines()
    except OSError:
        logger.warning(f"RULE_FIXER: Cannot read {full_path}")
        return ""

    logger.info(f"RULE_FIXER: Attempting {bug_type} fix for {file_rel}:{line_num}")

    diff = ""
    if bug_type == "LINTING":
        diff = _fix_linting(file_rel, lines, line_num, root_cause)
    elif bug_type == "SYNTAX":
        diff = _fix_syntax(file_rel, lines, line_num, root_cause, error_msg)
    elif bug_type == "INDENTATION":
        diff = _fix_indentation(file_rel, lines, line_num)
    elif bug_type == "IMPORT":
        diff = _fix_import(file_rel, lines, line_num, root_cause, error_msg)
    elif bug_type == "LOGIC":
        diff = _fix_logic(file_rel, lines, line_num, error_msg, traceback_str)
    elif bug_type == "TYPE_ERROR":
        diff = _fix_type_error(file_rel, lines, line_num, error_msg)

    if diff:
        logger.info(f"RULE_FIXER: Generated {bug_type} fix for {file_rel} ({len(diff)} chars)")
    else:
        logger.info(f"RULE_FIXER: Could not generate {bug_type} fix for {file_rel}")

    return diff


# ── Unified diff builders ────────────────────────────────────────

def _make_replace_diff(file_rel: str, lines: list[str], idx: int,
                       new_line: str, context: int = 3) -> str:
    """Build a diff that replaces a single line (0-indexed)."""
    old_line = lines[idx].rstrip("\n")
    new_line_clean = new_line.rstrip("\n")
    if old_line == new_line_clean:
        return ""

    ctx_start = max(0, idx - context)
    ctx_end = min(len(lines), idx + context + 1)

    hunk_lines = []
    old_count = 0
    new_count = 0

    for i in range(ctx_start, ctx_end):
        if i == idx:
            hunk_lines.append(f"-{old_line}")
            hunk_lines.append(f"+{new_line_clean}")
            old_count += 1
            new_count += 1
        else:
            hunk_lines.append(f" {lines[i].rstrip(chr(10))}")
            old_count += 1
            new_count += 1

    return (
        f"--- a/{file_rel}\n"
        f"+++ b/{file_rel}\n"
        f"@@ -{ctx_start + 1},{old_count} +{ctx_start + 1},{new_count} @@\n"
        + "\n".join(hunk_lines)
    )


def _make_delete_diff(file_rel: str, lines: list[str], idx: int, context: int = 3) -> str:
    """Build a diff that deletes a single line (0-indexed)."""
    ctx_start = max(0, idx - context)
    ctx_end = min(len(lines), idx + context + 1)

    hunk_lines = []
    old_count = 0
    new_count = 0

    for i in range(ctx_start, ctx_end):
        if i == idx:
            hunk_lines.append(f"-{lines[i].rstrip(chr(10))}")
            old_count += 1
        else:
            hunk_lines.append(f" {lines[i].rstrip(chr(10))}")
            old_count += 1
            new_count += 1

    return (
        f"--- a/{file_rel}\n"
        f"+++ b/{file_rel}\n"
        f"@@ -{ctx_start + 1},{old_count} +{ctx_start + 1},{new_count} @@\n"
        + "\n".join(hunk_lines)
    )


def _make_insert_before_diff(file_rel: str, lines: list[str], idx: int,
                              new_lines_text: list[str], context: int = 3) -> str:
    """Build a diff that inserts new lines BEFORE line at idx (0-indexed)."""
    ctx_start = max(0, idx - context)
    ctx_end = min(len(lines), idx + context + 1)

    hunk_lines = []
    old_count = 0
    new_count = 0

    for i in range(ctx_start, ctx_end):
        if i == idx:
            # Insert new lines before this line
            for nl in new_lines_text:
                hunk_lines.append(f"+{nl.rstrip(chr(10))}")
                new_count += 1
        hunk_lines.append(f" {lines[i].rstrip(chr(10))}")
        old_count += 1
        new_count += 1

    return (
        f"--- a/{file_rel}\n"
        f"+++ b/{file_rel}\n"
        f"@@ -{ctx_start + 1},{old_count} +{ctx_start + 1},{new_count} @@\n"
        + "\n".join(hunk_lines)
    )


# ── LINTING fixes ────────────────────────────────────────────────

def _fix_linting(file_rel: str, lines: list[str], line_num: int, root_cause: str) -> str:
    """Remove unused imports or trailing whitespace."""
    # If we have a specific line, check if it's an import
    if line_num > 0 and line_num <= len(lines):
        idx = line_num - 1
        line = lines[idx]
        if line.strip().startswith("import ") or line.strip().startswith("from "):
            return _make_delete_diff(file_rel, lines, idx)

    # Scan for unused imports
    for i, line in enumerate(lines):
        stripped = line.strip()
        match = re.match(r"^import\s+(\w+)\s*$", stripped)
        if match:
            name = match.group(1)
            # Count uses in all other lines (skip comments and the import itself)
            uses = 0
            for j, other in enumerate(lines):
                if j != i and not other.strip().startswith("#"):
                    if re.search(rf'\b{re.escape(name)}\b', other):
                        uses += 1
            if uses == 0:
                logger.info(f"RULE_FIXER: Removing unused import '{name}' at line {i + 1}")
                return _make_delete_diff(file_rel, lines, i)

    return ""


# ── SYNTAX fixes ─────────────────────────────────────────────────

def _fix_syntax(file_rel: str, lines: list[str], line_num: int,
                root_cause: str, error_msg: str) -> str:
    """Fix missing colon, missing parenthesis, etc."""
    if line_num <= 0 or line_num > len(lines):
        return ""

    idx = line_num - 1
    line = lines[idx]
    stripped = line.rstrip()

    # Missing colon after def/class/if/for/while/else/elif/try/except/finally/with
    keywords = ("def ", "class ", "if ", "for ", "while ", "else", "elif ", "try", "except", "finally", "with ")
    if any(stripped.lstrip().startswith(kw) for kw in keywords) and not stripped.endswith(":"):
        return _make_replace_diff(file_rel, lines, idx, stripped + ":\n")

    return ""


# ── INDENTATION fixes ────────────────────────────────────────────

def _fix_indentation(file_rel: str, lines: list[str], line_num: int) -> str:
    """Fix indentation to 4 spaces."""
    if line_num <= 0 or line_num > len(lines):
        return ""

    idx = line_num - 1
    line = lines[idx]

    expected_indent = _guess_expected_indent(lines, idx)
    current_indent = len(line) - len(line.lstrip())

    if current_indent != expected_indent:
        new_line = " " * expected_indent + line.lstrip()
        return _make_replace_diff(file_rel, lines, idx, new_line)

    return ""


def _guess_expected_indent(lines: list[str], idx: int) -> int:
    for i in range(idx - 1, -1, -1):
        prev = lines[i]
        if prev.strip():
            prev_indent = len(prev) - len(prev.lstrip())
            if prev.rstrip().endswith(":"):
                return prev_indent + 4
            return prev_indent
    return 0


# ── IMPORT fixes ─────────────────────────────────────────────────

def _fix_import(file_rel: str, lines: list[str], line_num: int,
                root_cause: str, error_msg: str) -> str:
    """Fix import-related errors: NameError typos, unused imports."""
    name_match = re.search(r"name '(\w+)' is not defined", error_msg)
    if name_match:
        undefined_name = name_match.group(1)
        return _fix_name_error(file_rel, lines, line_num, undefined_name)

    # Remove unused import at the specified line
    if line_num > 0 and line_num <= len(lines):
        idx = line_num - 1
        if lines[idx].strip().startswith(("import ", "from ")):
            return _make_delete_diff(file_rel, lines, idx)

    return ""


def _fix_name_error(file_rel: str, lines: list[str], line_num: int, undefined_name: str) -> str:
    """Fix NameError by finding the closest matching variable name (typo correction)."""
    defined_names: set[str] = set()

    for line in lines:
        stripped = line.strip()
        param_match = re.search(r'def\s+\w+\((.*?)\)', stripped)
        if param_match:
            for p in param_match.group(1).split(","):
                p = p.strip().split("=")[0].split(":")[0].strip()
                if p and p != "*" and not p.startswith("**"):
                    defined_names.add(p)
        assign_match = re.match(r'(\w+)\s*=', stripped)
        if assign_match:
            defined_names.add(assign_match.group(1))
        import_match = re.match(r'import\s+(\w+)', stripped)
        if import_match:
            defined_names.add(import_match.group(1))
        from_match = re.match(r'from\s+\S+\s+import\s+(.*)', stripped)
        if from_match:
            for name in from_match.group(1).split(","):
                name = name.strip().split(" as ")[-1].strip()
                if name:
                    defined_names.add(name)

    best_match = None
    best_distance = float("inf")
    for name in defined_names:
        dist = _edit_distance(undefined_name, name)
        if dist < best_distance and dist <= 2:
            best_distance = dist
            best_match = name

    if best_match and best_match != undefined_name:
        logger.info(f"RULE_FIXER: Replacing '{undefined_name}' → '{best_match}' (edit distance {best_distance})")
        for i in range(len(lines)):
            if re.search(rf'\b{re.escape(undefined_name)}\b', lines[i]):
                new_line = re.sub(rf'\b{re.escape(undefined_name)}\b', best_match, lines[i])
                return _make_replace_diff(file_rel, lines, i, new_line)

    return ""


def _edit_distance(a: str, b: str) -> int:
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]


# ── LOGIC fixes ──────────────────────────────────────────────────

def _fix_logic(file_rel: str, lines: list[str], line_num: int,
               error_msg: str, traceback_str: str) -> str:
    """Fix simple logic errors: operator swaps, zero-division guards."""
    combined = error_msg + " " + traceback_str

    # ZeroDivisionError: add a guard
    if "ZeroDivisionError" in combined:
        return _fix_zero_division(file_rel, lines, line_num, combined)

    # AssertionError with actual vs expected → try operator swap
    if "assert" in combined.lower() or "AssertionError" in combined:
        return _fix_assertion_operator_swap(file_rel, lines, line_num, combined)

    return ""


def _fix_zero_division(file_rel: str, lines: list[str], line_num: int, context: str) -> str:
    """Add zero-division guard: if b == 0: return 0."""
    target_idx = None
    if line_num > 0 and line_num <= len(lines):
        # Check if there's a division on or near this line
        for check in range(max(0, line_num - 3), min(len(lines), line_num + 3)):
            if re.search(r'\S\s*/\s*\S', lines[check]) and "return" in lines[check]:
                target_idx = check
                break
        if target_idx is None and "/" in lines[line_num - 1]:
            target_idx = line_num - 1

    if target_idx is None:
        for i, line in enumerate(lines):
            if "return" in line and re.search(r'\S\s*/\s*\S', line):
                target_idx = i
                break

    if target_idx is None:
        return ""

    line = lines[target_idx]
    indent = " " * (len(line) - len(line.lstrip()))

    # Extract divisor variable: "return a / b" → b
    div_match = re.search(r'/\s*(\w+)', line)
    if not div_match:
        return ""

    divisor = div_match.group(1)
    guard_lines = [
        f"{indent}if {divisor} == 0:\n",
        f"{indent}    return 0\n",
    ]

    return _make_insert_before_diff(file_rel, lines, target_idx, guard_lines)


def _fix_assertion_operator_swap(file_rel: str, lines: list[str], line_num: int,
                                  context: str) -> str:
    """
    Detect assertion failures like 'assert -1 == 5' and swap the arithmetic operator
    in the function that produced the wrong result.
    """
    # Try to find function name and expected/actual values
    func_name = None
    where_match = re.search(r'where\s+.*?=\s*(\w+)\(', context)
    if where_match:
        func_name = where_match.group(1)

    # Find the function body
    func_start = None
    func_end = None

    if func_name:
        for i, line in enumerate(lines):
            if re.search(rf'def\s+{re.escape(func_name)}\s*\(', line):
                func_start = i
                indent_level = len(line) - len(line.lstrip())
                for j in range(i + 1, len(lines)):
                    stripped = lines[j].strip()
                    if stripped and not stripped.startswith("#"):
                        line_indent = len(lines[j]) - len(lines[j].lstrip())
                        if line_indent <= indent_level:
                            func_end = j
                            break
                if func_end is None:
                    func_end = len(lines)
                break

    if func_start is None:
        if line_num > 0:
            func_start = max(0, line_num - 5)
            func_end = min(len(lines), line_num + 5)
        else:
            return ""

    # Operator swap pairs — try each on return/assignment lines in the function
    swaps = [("-", "+"), ("+", "-"), ("*", "/"), ("/", "*"),
             (">", "<"), ("<", ">"), (">=", "<="), ("<=", ">=")]

    for old_op, new_op in swaps:
        for i in range(func_start, func_end):
            line = lines[i]
            if "return" not in line and "=" not in line:
                continue
            if line.strip().startswith("#"):
                continue

            # Look for "X old_op Y" pattern (with spaces around operator)
            # Use a concrete regex per operator, not escaping tricks
            esc_old = re.escape(old_op)
            esc_new = re.escape(new_op)
            pattern = rf'(\w+\s*){esc_old}(\s*\w+)'

            match = re.search(pattern, line)
            if match:
                # Make sure we're not matching inside a comment
                comment_pos = line.find("#")
                if comment_pos >= 0 and match.start() > comment_pos:
                    continue

                # Perform the swap
                new_line = line[:match.start()] + re.sub(esc_old, new_op, match.group(), count=1) + line[match.end():]
                if new_line != line:
                    logger.info(f"RULE_FIXER: Operator swap '{old_op}' → '{new_op}' at line {i + 1}")
                    return _make_replace_diff(file_rel, lines, i, new_line)

    return ""


# ── TYPE_ERROR fixes ─────────────────────────────────────────────

def _fix_type_error(file_rel: str, lines: list[str], line_num: int, error_msg: str) -> str:
    """Fix obvious type mismatches: int()/str() casts."""
    if line_num <= 0 or line_num > len(lines):
        return ""

    idx = line_num - 1
    line = lines[idx]

    # "can only concatenate str (not 'int') to str" → wrap with str()
    if "can only concatenate str" in error_msg and "int" in error_msg:
        match = re.search(r'(\+\s*)(\w+)', line)
        if match:
            var = match.group(2)
            new_line = line[:match.start()] + match.group(1) + f"str({var})" + line[match.end():]
            if new_line != line:
                return _make_replace_diff(file_rel, lines, idx, new_line)

    # "unsupported operand type(s) for +: 'int' and 'str'" → wrap with int()
    if "unsupported operand" in error_msg and "'int' and 'str'" in error_msg:
        match = re.search(r'(\+\s*)(\w+)', line)
        if match:
            var = match.group(2)
            new_line = line[:match.start()] + match.group(1) + f"int({var})" + line[match.end():]
            if new_line != line:
                return _make_replace_diff(file_rel, lines, idx, new_line)

    return ""
