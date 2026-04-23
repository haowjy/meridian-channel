"""Python wrapper for mermaid diagram validation via bundled JS.

Requires Node.js on PATH. The bundled mermaid-validator.bundle.js file
must exist alongside this module.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Bundle path relative to this module
BUNDLE_PATH = Path(__file__).parent / "mermaid-validator.bundle.js"

# Validation timeout per block
TIMEOUT_SECS = 10


class NodeNotFoundError(RuntimeError):
    """Raised when node is not available on PATH."""


class BundleNotFoundError(EnvironmentError):
    """Raised when the JS bundle is missing (packaging error)."""


@dataclass
class BlockResult:
    """Result of validating one mermaid block."""

    file: str  # relative to root
    line: int  # block start line (1-indexed)
    valid: bool
    error: str | None = None


@dataclass
class MermaidValidationResult:
    """Complete validation result for a file or directory."""

    path: str
    total_blocks: int
    valid_blocks: int
    invalid_blocks: int
    has_errors: bool
    results: list[BlockResult]


def validate_path(path: Path) -> MermaidValidationResult:
    """Validate all mermaid blocks in a file or directory.

    Args:
        path: File or directory to validate

    Returns:
        MermaidValidationResult with per-block results

    Raises:
        NodeNotFoundError: If Node.js is not on PATH
        BundleNotFoundError: If the JS bundle is missing (packaging error)
        FileNotFoundError: If the path does not exist
    """
    # Node.js preflight
    if shutil.which("node") is None:
        raise NodeNotFoundError(
            "Node.js is required for mermaid validation. "
            "Install Node.js and ensure 'node' is on PATH."
        )

    # Bundle existence check
    if not BUNDLE_PATH.exists():
        raise BundleNotFoundError(
            "mermaid-validator.bundle.js not found; this is a packaging error. "
            f"Expected at: {BUNDLE_PATH}"
        )

    # Path validation
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    # Collect markdown files
    if path.is_dir():
        md_files = sorted(path.rglob("*.md"))
        root = path
    else:
        md_files = [path]
        root = path.parent

    all_results: list[BlockResult] = []

    # Import here to avoid circular imports
    from meridian.lib.markdown.extract import extract_file

    for md_file in md_files:
        doc = extract_file(md_file)
        if doc.error:
            continue

        rel = _rel(md_file, root)

        for block in doc.fenced_blocks:
            # Case-insensitive mermaid check
            if block.language.lower() != "mermaid":
                continue
            result = _validate_block(block.content, rel, block.start_line)
            all_results.append(result)

    valid = sum(1 for r in all_results if r.valid)
    invalid = len(all_results) - valid

    return MermaidValidationResult(
        path=path.as_posix(),
        total_blocks=len(all_results),
        valid_blocks=valid,
        invalid_blocks=invalid,
        has_errors=invalid > 0,
        results=all_results,
    )


def _validate_block(content: str, file: str, line: int) -> BlockResult:
    """Validate a single mermaid block by calling the bundled JS validator."""
    # Write content to temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".mmd",
        encoding="utf-8",
        delete=False,
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        proc = subprocess.run(
            ["node", str(BUNDLE_PATH), str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECS,
        )
    except subprocess.TimeoutExpired:
        return BlockResult(file=file, line=line, valid=False, error="validation timed out")
    finally:
        tmp_path.unlink(missing_ok=True)

    if proc.returncode == 0:
        return BlockResult(file=file, line=line, valid=True)

    # Parse error from JSON output
    error_msg: str | None = None
    try:
        parsed = json.loads(proc.stdout)
        error_msg = parsed.get("error")
    except (json.JSONDecodeError, KeyError):
        error_msg = proc.stdout.strip() or proc.stderr.strip() or "parse error"

    return BlockResult(file=file, line=line, valid=False, error=error_msg)


def _rel(path: Path, root: Path) -> str:
    """Get path relative to root as forward-slash string."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


__all__ = [
    "BlockResult",
    "BundleNotFoundError",
    "MermaidValidationResult",
    "NodeNotFoundError",
    "validate_path",
]
