# Prompts Directory

This directory contains prompt templates used by the knowledge service.

## Structure

Each prompt should be in its own file with the naming pattern: `{prompt_name}.yaml` (or `.json`, `.txt`)

Available prompt names:
- `entity_extraction` - For extracting entities from text
- `relation_extraction` - For extracting relationships between entities
- `query_classification` - For classifying query types
- `filter_extraction` - For extracting filters from queries

## File Formats

### YAML Format (Recommended)

```yaml
system: |
  Your system prompt here...
  Multi-line supported.
user: "Your human prompt template with {variables}"
```

### JSON Format

```json
{
  "system": "Your system prompt here...",
  "user": "Your human prompt template with {variables}"
}
```

### Plain Text Format

```
System prompt content here...
---
Human prompt template with {variables}
```

If no `---` separator is found, entire file is treated as system prompt.

## Configuration

Set the `PROMPT_SOURCE` environment variable to point to this directory:

```bash
# For file-based prompts (directory path)
PROMPT_SOURCE=/path/to/prompts

# For API-based prompts (base URL)
PROMPT_SOURCE=https://api.example.com/prompts
```

If not set, default prompts (hardcoded) will be used.

## Usage

The service automatically loads prompts from this directory when `PROMPT_SOURCE` points to it.
Each prompt file should contain both `system` and `user` keys/templates.


