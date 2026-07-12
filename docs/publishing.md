# Publishing PyWorkflow to PyPI

This guide walks you through building, validating, and publishing the **PyWorkflow** package to PyPI (Python Package Index).

---

## 1. Prerequisites

First, ensure you have the necessary packaging and distribution tools installed:

```bash
python3 -m pip install --upgrade pip build twine
```

---

## 2. Build the Package

To package the source code and generate the distribution archives (source distribution `.tar.gz` and wheel `.whl`):

```bash
python3 -m build
```

This will generate files in a newly created `dist/` directory:
- `dist/pyworkflow-0.1.0.tar.gz`
- `dist/pyworkflow-0.1.0-py3-none-any.whl`

---

## 3. Package Validation

Always check your package definition and metadata description rendering before uploading:

```bash
python3 -m twine check dist/*
```

This command runs checks to ensure that the `README.md` content compiles correctly as HTML and that PyPI will be able to display it without errors.

---

## 4. Publishing to TestPyPI (Recommended)

Before uploading to the real index, it is highly recommended to upload your package to **TestPyPI** to verify that everything looks correct and installs properly:

1. **Upload to TestPyPI**:
   ```bash
   python3 -m twine upload --repository testpypi dist/*
   ```
   *Note: You will be prompted to enter your TestPyPI username (use `__token__`) and password (your TestPyPI API token value starting with `pypi-`).*

2. **Test Installation**:
   Verify you can install it in a clean virtual environment:
   ```bash
   python3 -m pip install --index-url https://test.pypi.org/simple/ --no-deps pyworkflow
   ```

---

## 5. Publishing to PyPI

Once you have verified the release on TestPyPI, publish to the official package index:

```bash
python3 -m twine upload dist/*
```

*Note: Use `__token__` as the username and your official PyPI API token as the password.*

---

## 6. Automation with Makefile

You can run release validation checks using the `Makefile` in the root of the project:

- **Build and Twine Check**:
  ```bash
  make release
  ```
