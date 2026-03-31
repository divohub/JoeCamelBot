# Shnyaga-Bot Operational Guide for AI Agents

Welcome, fellow agent! This document contains the necessary context, commands, and guidelines for working on the Shnyaga-Bot codebase.

## 🚀 Project Overview

Shnyaga-Bot is a Telegram bot that tracks "shnyaga" (activities/achievements) for a group of friends. It uses Google Gemini AI to score these activities and maintain a competitive leaderboard.

### Key Components:
- `main.py`: Telegram bot handlers (using aiogram), scheduler (apscheduler), and interactive logic.
- `database.py`: Asynchronous SQLite database management (using aiosqlite).
- `ai_logic.py`: Integration with Google Gemini API (using `google-genai` SDK) for activity scoring, "anti-shnyaga" detection, and personality.
- `Dockerfile` & `docker-compose.yml`: Containerization and orchestration.

---

## 🛠 Build & Run Commands

### Development Environment Setup
1. Create a virtual environment: `python -m venv venv`
2. Activate it: `source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`

### Running the Bot
- **Manual Execution**: `python main.py`
- **Using Docker (Recommended)**:
  - Build and start: `docker-compose up -d --build`
  - View logs: `docker logs -f shnyaga-bot`
  - Stop: `docker-compose down`

### Interactive Configuration
- `CHANCE_REACT`: The probability (0.0 to 1.0) that the bot will respond to a random message in the chat. Direct mentions or replies are always handled (100%).
- `MIN_VOTES`: Number of user approvals needed for "Mega-Shnyaga" (150 points).

### Testing & Linting
Currently, the project does not have a formal test suite or linter configuration.
- **Proposed Test Runner**: Use `pytest`. Run all tests with `pytest`.
- **Proposed Linter**: Use `flake8` or `pylint`. Run with `flake8 .`.
- **Proposed Formatter**: Use `black`. Run with `black .`.

---

## 🎨 Code Style Guidelines

### Naming Conventions
- **Files**: Use `snake_case.py`.
- **Functions/Variables**: Use `snake_case`.
- **Classes**: Use `PascalCase`.
- **Constants**: Use `UPPER_SNAKE_CASE`.

### Imports
- Organize imports in three groups: standard library, third-party, and local modules.
- Use absolute imports for clarity.

### Types & Documentation
- **Type Hints**: Use type hints for all function arguments and return values.
- **Docstrings**: Provide Google-style docstrings for all non-trivial functions and classes.

### Error Handling
- Use `try/except` blocks for all I/O operations (API calls, database queries).
- Log errors using the `logging` module. Avoid `print()`.
- Provide meaningful fallback mechanisms (e.g., default scores in `ai_logic.py`).

### Asynchronous Programming
- Use `async` and `await` for all I/O-bound tasks.
- Avoid blocking the main event loop with long-running synchronous code.

---

## 🧠 Feature Branching & Code Review Policy
To maintain code quality and prevent bugs, we adhere to the following workflow:

1.  **Branching**: Every new feature, bug fix, or major refactor MUST be done in its own branch.
    - Branch naming convention: `feature/<feature-name>` (e.g., `feature/ai-memory-audit`) or `fix/<bug-name>`.
2.  **Code Review**: 
    - **NEVER** commit or merge directly into `main`.
    - Always create a Pull Request (PR) for any new code using the GitHub CLI (`gh`).
    - AI agents must request a human review before a PR is marked as ready for merge.
3.  **Docker Management**:
    - **NEVER** run `docker-compose up` or `down` as an agent. The user will handle the container lifecycle and restarts.
    - If you make changes that require a rebuild, clearly notify the user: "Code updated, please restart the container."

---

## 📂 Project Structure & Expansion

### Adding New Commands
1. Register the command in `main.py` using `@dp.message(Command("your_command"))`.
2. Implement the handler function with proper error handling and database interactions.

### Database Modifications
1. Add new tables or modify existing ones in `database.py`'s `init_db()` function.
2. Implement new database access functions (e.g., `get_X`, `add_X`) in `database.py`.
3. Use `aiosqlite` for all database interactions to maintain asynchronicity.

### AI & Personality Updates
1. Modify the `SYSTEM_PROMPT` in `ai_logic.py` to adjust the bot's tone or scoring logic.
2. Ensure the AI response remains a valid JSON by carefully managing the prompt and parsing logic.

---

## 📋 Best Practices

1. **Keep it simple**: The project is designed to be lightweight and easy to maintain.
2. **Be consistent**: Follow existing patterns for database access and bot interaction.
3. **Log everything**: Use different log levels (`INFO`, `WARNING`, `ERROR`) to track bot activity and troubleshoot issues.
4. **Environment variables**: Store all sensitive information (tokens, keys) in a `.env` file and never commit it to version control. Use `.env.example` as a template.
5. **Docker Volume**: Ensure that the database file is stored in a volume (as configured in `docker-compose.yml`) to prevent data loss.

---

## 🧪 Testing (Future)

To run a single test (when implemented):
`pytest tests/test_file.py::test_function_name`

Example of adding a test:
1. Create a `tests/` directory.
2. Add a `test_database.py` file to test database operations.
3. Use `pytest-asyncio` for testing asynchronous functions.

---

*Note: This guide is intended for AI agents. For humans, please refer to the README.md if it exists.*
