# Contributing to PyWorkflow

Welcome to PyWorkflow! We're excited that you want to help make this framework better. As an open-source project, we welcome contributions of all forms—from bug fixes to feature proposals, documentation enhancements, and testing.

## Code of Conduct

By participating, you agree to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting Started

1. **Fork the Repository**: Create a fork of `pyworkflow/pyworkflow` on GitHub.
2. **Clone Locally**: Clone your fork to your development environment:
   ```bash
   git clone https://github.com/<your-username>/pyworkflow.git
   cd pyworkflow
   ```
3. **Setup Environment**: We recommend developing inside a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
4. **Install Dependencies**: Install the package along with development extras:
   ```bash
   pip install -r requirements.txt
   pip install -e .[all]
   ```

## Development Workflow

### Coding Standards
- Follow PEP 8 guidelines.
- Use meaningful type hints for all public APIs.
- Write docstrings for all modules, classes, and methods.

### Running Tests
We use `pytest` for all unit and integration testing:
```bash
pytest
```
To run tests with coverage reporting:
```bash
pytest --cov=pyworkflow --cov-report=html
```
Please ensure all tests pass and that your code modifications do not drop coverage (our target is 90%+).

## Submitting Pull Requests

1. Create a new branch describing your fix or feature (e.g. `feature/process-workers` or `bugfix/sqlite-checkpoint`).
2. Implement your changes and add corresponding tests.
3. Verify tests, linting, and type checking run clean locally.
4. Commit your changes using descriptive commit messages.
5. Push to your fork and submit a Pull Request (PR) to the `main` branch.
6. Refer to the Pull Request template to fill out details.
