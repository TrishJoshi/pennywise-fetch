# PennyWise Backup Sync Service

## Environment Setup

This project uses `pyenv` for Python version management and virtual environments.

### Prerequisites
- `pyenv` installed
- Python 3.10+ (recommended)

### Setup
1.  **Create/Activate Environment**:
    The project is configured to use the `pwf` virtual environment.
    ```bash
    pyenv virtualenv 3.10.16 pwf  # Or your preferred python version
    pyenv local pwf
    ```

2.  **Install Dependencies**:
    For development (includes testing tools):
    ```bash
    pip install -r requirements-dev.txt
    ```
    For production:
    ```bash
    pip install -r requirements.txt
    ```

## Running Tests
Run tests using `pytest`:
```bash
pytest
```
