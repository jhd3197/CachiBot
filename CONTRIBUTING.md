# Contributing to Cachibot

Thank you for your interest in contributing to Cachibot! 🛡️

## Getting Started

### Prerequisites

- Python 3.10 or higher
- An Anthropic API key

### Development Setup

1. **Clone the repository**

```bash
git clone https://github.com/jhd3197/cachibot.git
cd cachibot
```

2. **Create a virtual environment**

```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# Unix/macOS
source venv/bin/activate
```

3. **Install in development mode**

```bash
pip install -e ".[dev]"
```

4. **Set up your API key**

```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "your-api-key"

# Unix/macOS
export ANTHROPIC_API_KEY="your-api-key"
```

## Development Workflow

### Running Tests

```bash
pytest
```

### Linting

```bash
ruff check src/
ruff format src/
```

### Type Checking

```bash
mypy src/cachibot
```

## Code Style

- We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting
- Type hints are required for all public functions
- Docstrings follow Google style

### Example

```python
def process_file(path: str, encoding: str = "utf-8") -> str:
    """
    Process a file and return its contents.
    
    Args:
        path: Path to the file to process
        encoding: File encoding (default: utf-8)
        
    Returns:
        The processed file contents
        
    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    ...
```

## Adding New Tools

Tools are the actions Cachibot can take. To add a new tool:

1. Create a new file in `src/cachibot/tools/`
2. Inherit from `BaseTool`
3. Implement the `execute` method
4. Register in `agent.py`

### Example Tool

```python
from cachibot.tools import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"
    
    def execute(self, param1: str, **kwargs) -> ToolResult:
        try:
            # Do something
            return ToolResult.ok("Success!")
        except Exception as e:
            return ToolResult.fail(str(e))
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to your fork (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### PR Guidelines

- Keep PRs focused on a single feature or fix
- Update documentation if needed
- Add tests for new functionality
- Follow existing code style

## Reporting Issues

When reporting issues, please include:

- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Any error messages

## Questions?

Feel free to open an issue for questions or join discussions.

---

Made with 🛡️ by [jhd3197](https://jhd3197.com)
