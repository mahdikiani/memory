"""Script to generate schemas.py from Pydantic models."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from apps.knowledge.schema_generator import generate_schemas_file


def main() -> None:
    """Generate schemas.py file."""
    schema_content = generate_schemas_file()

    schema_file = Path(__file__).parent / "schemas.py"
    schema_file.write_text(schema_content)


if __name__ == "__main__":
    main()
