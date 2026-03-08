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

## Test

```bash
uv run pytest-llm
uv run pyright
```

## Run from source

```bash
uv run meridian --help
```
