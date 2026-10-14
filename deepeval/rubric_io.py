"""Complete-file publication without overwriting existing user output."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_new_bytes(output, payload):
    """Flush a sibling temporary file then link it to an unoccupied path.

    Hard-link publication is atomic and fails if the destination exists.
    Filesystems without hard-link support fail closed rather than replacing
    existing data or exposing partial output.
    """
    output = Path(output)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output.parent, prefix=".rubric-", suffix=".tmp", delete=False
        ) as target:
            temporary = Path(target.name)
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
