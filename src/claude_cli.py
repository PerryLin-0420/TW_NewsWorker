"""
找 claude.exe 路徑，優先序：
1. config.json 的 claude_exe 欄位（使用者手動指定）
2. CLAUDE_CODE_EXECPATH 環境變數（Claude Code 自動注入）
3. 常見安裝路徑 fallback
"""
import json
import os
import re
import subprocess
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

_CLAUDE_CODE_BASE = Path.home() / "AppData" / "Roaming" / "Claude" / "claude-code"

# The CLI reports auth failures on stdout with an empty stderr, so match on text.
_AUTH_ERROR_MARKERS = (
    "failed to authenticate",
    "oauth",
    "not logged in",
    "/login",
    "invalid api key",
)


class ClaudeError(RuntimeError):
    """The claude CLI could not produce a result."""


class ClaudeAuthError(ClaudeError):
    """The CLI ran but holds no usable credentials — needs an interactive login."""


def _version_key(name: str) -> tuple:
    """Numeric version ordering; plain string sort ranks 2.1.9 above 2.1.221."""
    return tuple(int(p) if p.isdigit() else -1 for p in re.split(r"[.\-+_]", name))


def _find_latest_claude_exe() -> str | None:
    """動態找 claude-code 下版本號最大的子資料夾內的 claude.exe。"""
    if not _CLAUDE_CODE_BASE.is_dir():
        return None
    # Newer installs nest the exe one level deeper: <version>/<hash>/claude.exe
    found = list(_CLAUDE_CODE_BASE.glob("*/claude.exe")) + list(_CLAUDE_CODE_BASE.glob("*/*/claude.exe"))
    candidates = sorted(
        found,
        key=lambda p: _version_key(p.relative_to(_CLAUDE_CODE_BASE).parts[0]),
        reverse=True,
    )
    for exe in candidates:
        if exe.is_file():
            return str(exe)
    return None


def find_claude_exe() -> str:
    cfg_path = ROOT / "config.json"
    if cfg_path.exists():
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        if cfg.get("claude_exe"):
            return cfg["claude_exe"]

    env_path = os.environ.get("CLAUDE_CODE_EXECPATH", "")
    if env_path and Path(env_path).is_file():
        return env_path

    latest = _find_latest_claude_exe()
    if latest:
        return latest

    # 最後試 PATH（Linux/Mac 或 PATH 有設好的環境）
    try:
        result = subprocess.run(
            ["where", "claude"] if os.name == "nt" else ["which", "claude"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip().splitlines()[0]
    except Exception:
        pass

    raise FileNotFoundError(
        "找不到 claude.exe。請在 config.json 中設定 claude_exe 欄位，"
        "例如: \"claude_exe\": \"C:\\\\...\\\\claude.exe\""
    )


def auth_hint() -> str:
    """Exact command to restore credentials, with the resolved exe path."""
    try:
        exe = find_claude_exe()
    except Exception:
        exe = "claude"
    return (
        "claude CLI 未登入。請在互動式終端機執行以下指令建立長期 token"
        "（適合無人排程，需 Claude 訂閱）:\n"
        f'  & "{exe}" setup-token'
    )


def auth_status() -> dict:
    """
    Ask the CLI for its own auth state — cheap, machine-readable, and lets the
    caller fail fast instead of burning one failing invocation per region.
    Returns {} when the state cannot be determined, so this check can never
    become a new failure point of its own.
    """
    try:
        exe = find_claude_exe()
        result = subprocess.run(
            [exe, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return json.loads((result.stdout or "").strip())
    except Exception:
        return {}


def call_claude(prompt: str, timeout: int = 120) -> str:
    exe = find_claude_exe()
    result = subprocess.run(
        [exe, "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    if result.returncode == 0:
        return result.stdout.strip()

    # Check both streams: auth failures land on stdout, leaving stderr empty.
    detail = (result.stderr or "").strip() or (result.stdout or "").strip()
    if any(marker in detail.lower() for marker in _AUTH_ERROR_MARKERS):
        raise ClaudeAuthError(detail or "claude CLI 認證失效")
    raise ClaudeError(detail or f"claude CLI 回傳非零狀態碼: {result.returncode}")
