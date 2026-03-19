# Contributing to XROSS

This document provides guidelines for contributing to the project.

## Reporting issues

If you find a bug or have a feature request, please open an issue on the [GitHub issue tracker](https://github.com/nhayase/XROSS/issues). Include:

- A clear description of the problem or feature
- Steps to reproduce (for bugs)
- Your Python version and operating system
- Any relevant error messages or screenshots

## Development setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/XROSS.git
   cd XROSS
   ```

2. Install in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

3. Run the test suite:
   ```bash
   pytest
   ```

## Making changes

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes, ensuring:
   - New functionality includes tests in `tests/`
   - Code follows the existing style (PEP 8)
   - Docstrings are provided for public functions (NumPy style)

3. Run tests before submitting:
   ```bash
   pytest --cov=xross
   ```

4. Submit a pull request to the `main` branch.

## Code organisation

- **Physics / computation** → `xross/core.py`, `xross/xrr.py`, `xross/optimize.py`
- **File I/O** → `xross/fileio.py`
- **GUI** → `xross/gui/`
- **Tests** → `tests/`

Please keep GUI code separate from computational logic. All physics functions should work without any Tkinter imports.

## Code of Conduct

This project follows the
[Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

