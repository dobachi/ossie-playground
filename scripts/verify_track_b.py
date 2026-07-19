#!/usr/bin/env python
"""トラックB（0.2.0.dev0）の検証。

仕様リポジトリ同梱の公式コンバータ（converters/dbt）で dbt プロジェクトから
OSI 文書を生成し、それを出荷版 dbt Core が受理するかを確認する。

検証項目 V1 / V6 に対応する。計画は
content/research/topics/apache-ossie/notes/2026-07-19-verification-plan.md
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import yaml

from lib_ossie import (
    WORK, SPEC, hr, step, validate, schema_version_const, dbt, save_result, run,
)

PROJECT = WORK / "track-a" / "dbt-project"
OSI_DST = PROJECT / "OSI"
GEN = WORK / "track-b" / "generated"

results: dict = {"track": "B", "spec_version": "0.2.0.dev0", "checks": {}}


def ensure_converter() -> None:
    """PyPI 未公開のため、仕様リポジトリからソース導入する。"""
    proc = run([
        "uv", "pip", "install", "--python", "/opt/venv/bin/python",
        "--no-deps", "--offline",
        str(SPEC / "python"), str(SPEC / "converters" / "dbt"),
    ])
    if proc.returncode != 0:
        print(proc.stdout, proc.stderr)
        raise SystemExit("コンバータの導入に失敗")


def main() -> None:
    hr("トラックB: 公式コンバータの出力を出荷版 dbt に通す")

    print(f"main スキーマの version 制約: const = {schema_version_const('0.2.0.dev0')!r}")

    ensure_converter()
    GEN.mkdir(parents=True, exist_ok=True)

    # トラックAの成果物（semantic_manifest.json）を入力にする
    sem_manifest = PROJECT / "target" / "semantic_manifest.json"
    if not sem_manifest.exists():
        raise SystemExit("先に make verify-a を実行して semantic_manifest.json を作ること")

    # --- 1. 公式コンバータで dbt -> OSI ---
    step("1. 公式コンバータ (ossie-dbt msi-to-osi) で dbt から OSI 文書を生成")
    out_yaml = GEN / "from_dbt.yaml"
    proc = run([
        "ossie-dbt", "msi-to-osi",
        "-i", str(sem_manifest),
        "-o", str(out_yaml),
        "--model-name", "sales_roundtrip",
    ])
    print((proc.stdout + proc.stderr).strip()[:800] or "(出力なし)")
    generated = out_yaml.exists()
    results["checks"]["converter_ran"] = {"passed": generated}
    if not generated:
        save_result("track_b", results)
        raise SystemExit("生成に失敗")

    doc = yaml.safe_load(out_yaml.read_text())
    emitted_version = doc.get("version")
    print(f"\n  生成物の形式        : YAML ({out_yaml.name})")
    print(f"  宣言されたバージョン: {emitted_version!r}")
    results["checks"]["emitted_version"] = emitted_version
    results["checks"]["emitted_format"] = "yaml"

    # --- 2. main のスキーマで検証 ---
    step("2. 生成物を main (0.2.0.dev0) のスキーマで検証")
    ok_main, out_main = validate(out_yaml, "0.2.0.dev0")
    print(f"  {out_main or '(出力なし)'}")
    results["checks"]["validate_against_main"] = {"passed": ok_main, "output": out_main}

    # --- 3. V6: 出荷版 dbt に取り込めるか ---
    step("V6. 生成物をそのまま出荷版 dbt に読ませる")
    print("  注記: dbt は OSI/ 配下の .json のみ走査するため、")
    print("        YAML のままでは発見されない。JSON に変換したうえで投入する。")
    as_json = GEN / "from_dbt.json"
    as_json.write_text(json.dumps(doc, ensure_ascii=False, indent=2, default=str))

    for f in OSI_DST.glob("*"):
        f.unlink()
    shutil.copy(as_json, OSI_DST / "from_dbt.json")

    proc = dbt(["parse"], PROJECT)
    accepted = proc.returncode == 0
    msg = (proc.stdout + proc.stderr)
    print(f"  結果: {'受理' if accepted else '拒否'}")
    if not accepted:
        for line in msg.splitlines():
            if "unsupported version" in line.lower() or "Parsing Error" in line:
                print(f"    {line.strip()}")
    results["checks"]["V6_shipped_dbt_accepts_official_output"] = {
        "accepted": accepted,
        "message": msg[-600:],
    }

    # --- 4. V1: バージョン文字列だけ書き換えたらどうなるか ---
    step("V1. version だけ 0.1.1 に書き換えて再投入")
    downgraded = dict(doc)
    downgraded["version"] = "0.1.1"
    down_path = GEN / "from_dbt_downgraded.json"
    down_path.write_text(json.dumps(downgraded, ensure_ascii=False, indent=2, default=str))

    down_yaml = GEN / "from_dbt_downgraded.yaml"
    down_yaml.write_text(yaml.safe_dump(downgraded, allow_unicode=True, sort_keys=False))
    ok_011, out_011 = validate(down_yaml, "0.1.1")
    print(f"  0.1.1 スキーマでの検証: {'通過' if ok_011 else '不通過'}")
    if not ok_011:
        for line in (out_011 or "").splitlines()[:6]:
            print(f"    {line}")

    for f in OSI_DST.glob("*"):
        f.unlink()
    shutil.copy(down_path, OSI_DST / "from_dbt.json")
    proc = dbt(["parse"], PROJECT)
    accepted_down = proc.returncode == 0
    print(f"  dbt での取り込み      : {'受理' if accepted_down else '拒否'}")
    if not accepted_down:
        for line in (proc.stdout + proc.stderr).splitlines():
            if "Error" in line or "error" in line:
                print(f"    {line.strip()[:200]}")
                break
    results["checks"]["V1_version_downgrade"] = {
        "validates_against_011": ok_011,
        "validator_output": out_011,
        "dbt_accepted": accepted_down,
    }

    # 後始末: トラックAの正しい文書に戻す
    for f in OSI_DST.glob("*"):
        f.unlink()
    shutil.copy(WORK / "track-a" / "osi" / "sales.json", OSI_DST / "sales.json")

    save_result("track_b", results)
    hr("トラックB 完了")


if __name__ == "__main__":
    main()
