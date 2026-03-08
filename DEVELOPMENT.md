# Development

## Setup

```bash
git clone https://github.com/haowjy/meridian-channel.git
cd meridian-channel
uv sync --extra dev
```

## Verify

```bash
uv run meridian --version
uv run meridian doctor
```

## Install Validation

Use these when you want to verify the installed CLI behavior, not just `uv run`
from the checkout.

Editable install:

```bash
uv tool install --force --editable . --no-cache
```

Snapshot install from the current checkout:

```bash
uv tool install --force . --no-cache
```

Then verify the installed tool:

```bash
meridian --version
uv tool list
```

## Test

```bash
uv run pytest-llm
uv run pyright
```

## Run from source

```bash
uv run meridian --help
```
