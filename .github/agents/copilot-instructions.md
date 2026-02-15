# havachat-library-server Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-01-26

## Active Technologies
- Python 3.13 (per pyproject.toml: requires-python = ">=3.13,<3.14") + elevenlabs>=1.0.0, requests>=2.31.0, python-dotenv>=1.2.1, pydantic (via existing models), instructor>=1.0.0, openai>=1.0.0 or anthropic>=0.40.0 (via havachat.utils.llm_client) (001-notion-audio-processor)
- Filesystem (audio files at `<HAVACHAT_KNOWLEDGE_PATH>/<Topic>/<Sub-Type>/<ID>-<Name>.mp3`, Notion as metadata database) (001-notion-audio-processor)

- Python 3.14 (minimum required by constitution) (001-pregen-pipeline)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.14 (minimum required by constitution): Follow standard conventions

## Recent Changes
- 001-notion-audio-processor: Added Python 3.13 (per pyproject.toml: requires-python = ">=3.13,<3.14") + elevenlabs>=1.0.0, requests>=2.31.0, python-dotenv>=1.2.1, pydantic (via existing models), instructor>=1.0.0, openai>=1.0.0 or anthropic>=0.40.0 (via havachat.utils.llm_client)

- 001-pregen-pipeline: Added Python 3.14 (minimum required by constitution)

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
