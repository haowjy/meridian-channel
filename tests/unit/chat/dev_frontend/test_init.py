from pathlib import Path

from meridian.lib.chat import dev_frontend


def test_resolve_dev_frontend_root_prefers_explicit_path_over_env(monkeypatch, tmp_path: Path):
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    env_root = tmp_path / "env"
    env_root.mkdir()
    sibling = tmp_path / "sibling"
    sibling.mkdir()

    monkeypatch.setenv("MERIDIAN_DEV_FRONTEND_ROOT", str(env_root))
    monkeypatch.setattr(dev_frontend, "resolve_project_root", lambda: sibling.parent / "cli")

    resolved = dev_frontend.resolve_dev_frontend_root(explicit=str(explicit))

    assert resolved == explicit.resolve()


def test_resolve_dev_frontend_root_uses_env_when_explicit_blank(monkeypatch, tmp_path: Path):
    env_root = tmp_path / "frontend"
    env_root.mkdir()
    monkeypatch.setenv("MERIDIAN_DEV_FRONTEND_ROOT", str(env_root))

    resolved = dev_frontend.resolve_dev_frontend_root(explicit="   ")

    assert resolved == env_root.resolve()


def test_resolve_dev_frontend_root_uses_sibling_convention(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    cli_root = workspace / "meridian-cli"
    frontend_root = workspace / "meridian-web"
    cli_root.mkdir(parents=True)
    frontend_root.mkdir()
    monkeypatch.delenv("MERIDIAN_DEV_FRONTEND_ROOT", raising=False)
    monkeypatch.setattr(dev_frontend, "resolve_project_root", lambda: cli_root)

    resolved = dev_frontend.resolve_dev_frontend_root()

    assert resolved == frontend_root.resolve()


def test_resolve_dev_frontend_root_returns_none_when_sibling_missing(monkeypatch, tmp_path: Path):
    cli_root = tmp_path / "meridian-cli"
    cli_root.mkdir()
    monkeypatch.delenv("MERIDIAN_DEV_FRONTEND_ROOT", raising=False)
    monkeypatch.setattr(dev_frontend, "resolve_project_root", lambda: cli_root)

    assert dev_frontend.resolve_dev_frontend_root() is None


def test_resolve_dev_frontend_root_returns_none_when_project_root_lookup_fails(monkeypatch):
    monkeypatch.delenv("MERIDIAN_DEV_FRONTEND_ROOT", raising=False)

    def boom() -> Path:
        raise RuntimeError("no project root")

    monkeypatch.setattr(dev_frontend, "resolve_project_root", boom)

    assert dev_frontend.resolve_dev_frontend_root() is None


def test_validate_dev_prerequisites_rejects_missing_root(tmp_path: Path):
    missing = tmp_path / "missing"

    error = dev_frontend.validate_dev_prerequisites(missing)

    assert error == f"Frontend root does not exist or is not a directory: {missing}"


def test_validate_dev_prerequisites_rejects_missing_package_json(tmp_path: Path):
    root = tmp_path / "frontend"
    root.mkdir()

    error = dev_frontend.validate_dev_prerequisites(root)

    assert error == f"Frontend root is missing package.json: {root}"


def test_validate_dev_prerequisites_rejects_missing_node_modules(tmp_path: Path):
    root = tmp_path / "frontend"
    root.mkdir()
    (root / "package.json").write_text("{}")

    error = dev_frontend.validate_dev_prerequisites(root)

    assert error == (
        f"Frontend dependencies are missing at {root / 'node_modules'}. "
        f"Run: cd {root} && pnpm install"
    )


def test_validate_dev_prerequisites_accepts_installable_checkout(tmp_path: Path):
    root = tmp_path / "frontend"
    root.mkdir()
    (root / "package.json").write_text("{}")
    (root / "node_modules").mkdir()

    assert dev_frontend.validate_dev_prerequisites(root) is None
