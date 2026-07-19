"""検証スクリプト共通のユーティリティ。

仕様リポジトリ spec/ は固定コミットで取得済みである前提。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

WORK = Path("/work")
SPEC = WORK / "spec"
RESULTS = WORK / "docs" / "results"

TAG_011 = "osi-0.1.1-rc1"


def hr(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def step(msg: str) -> None:
    print(f"\n--- {msg}")


def run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess:
    """コマンドを実行し、結果をそのまま返す。失敗も観測対象なので既定では raise しない。"""
    proc = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True,
    )
    if check and proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"失敗: {' '.join(cmd)}")
    return proc


def git_show(ref: str, path: str) -> str:
    """spec リポジトリの特定リビジョンからファイル内容を取り出す。"""
    proc = run(["git", "show", f"{ref}:{path}"], cwd=SPEC, check=True)
    return proc.stdout


def prepare_validator(version: str) -> Path:
    """指定バージョンのバリデータを、期待するディレクトリ構造で展開する。

    0.1.1 の validate.py は --schema オプションを持たず、
    ``__file__.parent.parent / "core-spec" / "osi-schema.json"`` を
    決め打ちで読むため、その構造を再現する必要がある。

    Returns: 展開先の validate.py へのパス
    """
    root = Path(f"/tmp/validator-{version}")
    if root.exists():
        shutil.rmtree(root)
    (root / "validation").mkdir(parents=True)
    (root / "core-spec").mkdir(parents=True)

    if version == "0.1.1":
        (root / "validation" / "validate.py").write_text(
            git_show(TAG_011, "validation/validate.py")
        )
        (root / "core-spec" / "osi-schema.json").write_text(
            git_show(TAG_011, "core-spec/osi-schema.json")
        )
    else:  # main = 0.2.0.dev0
        shutil.copy(SPEC / "validation" / "validate.py", root / "validation" / "validate.py")
        shutil.copy(SPEC / "core-spec" / "osi-schema.json", root / "core-spec" / "osi-schema.json")

    return root / "validation" / "validate.py"


def validate(doc: Path, version: str) -> tuple[bool, str]:
    """公式バリデータで検証する。 (通ったか, 出力) を返す。"""
    validator = prepare_validator(version)
    proc = run([sys.executable, str(validator), str(doc)])
    out = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0, out


def schema_version_const(version: str) -> str:
    """スキーマが version に課している const 値を返す。"""
    root = prepare_validator(version)
    schema = json.loads((root.parent.parent / "core-spec" / "osi-schema.json").read_text())
    return schema["properties"]["version"].get("const")


def dbt(args: list[str], project: Path) -> subprocess.CompletedProcess:
    return run(["dbt", *args], cwd=project)


def dbt_failed_with(proc: subprocess.CompletedProcess, needle: str) -> bool:
    return needle.lower() in (proc.stdout + proc.stderr).lower()


def save_result(name: str, payload: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\n[記録] {path}")
