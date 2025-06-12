# Installation

This guide will help you install OntoCast and its dependencies.

## System Requirements

- Python 3.12 or higher
- uv (Python package installer)

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/growgraph/ontocast.git
cd ontocast
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
uv sync --dev
```

### 4. Install PreCommit

```bash
pre-commit install
```

## Verifying Installation

To verify that OntoCast is installed correctly, run:

```bash
uv run serve --help
```

You should see the help message with available command-line options.

## Next Steps

After installation, you can:

1. Read the [Quick Start](quickstart.md) guide
2. Configure OntoCast in the [Configuration](configuration.md) guide
3. Explore [Basic Usage](../examples/basic_usage.md) examples
4. Check the [API Reference](../reference/index.md) for detailed documentation 