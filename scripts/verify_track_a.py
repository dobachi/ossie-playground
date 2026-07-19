#!/usr/bin/env python
"""トラックA（0.1.1）の検証。

リリース版 0.1.1 に準拠した文書を、公式バリデータで検証したうえで
出荷版 dbt Core に取り込み、実際にクエリできるところまで確認する。

検証項目 V2 / V3 / V4 / V5 に対応する。計画は
content/research/topics/apache-ossie/notes/2026-07-19-verification-plan.md
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from lib_ossie import (
    WORK, hr, step, validate, schema_version_const, dbt, save_result, run,
)

PROJECT = WORK / "track-a" / "dbt-project"
OSI_SRC = WORK / "track-a" / "osi"
OSI_DST = PROJECT / "OSI"

results: dict = {"track": "A", "spec_version": "0.1.1", "checks": {}}


def main() -> None:
    hr("トラックA: リリース版 0.1.1 を出荷版 dbt に通す")

    print(f"0.1.1 スキーマの version 制約: const = {schema_version_const('0.1.1')!r}")

    # --- 前提: 投入する文書は必ず公式バリデータを通してから使う ---
    step("1. 自作の 0.1.1 文書を公式バリデータで検証")
    doc = OSI_SRC / "sales.json"
    ok, out = validate(doc, "0.1.1")
    print(out or "(出力なし)")
    results["checks"]["official_validation"] = {"passed": ok, "output": out}
    if not ok:
        raise SystemExit("自作文書が仕様に準拠していない。修正してからやり直すこと。")

    # --- dbt に取り込む ---
    step("2. dbt に取り込む")
    OSI_DST.mkdir(exist_ok=True)
    for f in OSI_DST.glob("*.json"):
        f.unlink()
    shutil.copy(doc, OSI_DST / doc.name)

    proc = dbt(["parse"], PROJECT)
    parsed = proc.returncode == 0
    print(proc.stdout[-1500:] if proc.stdout else "")
    if not parsed:
        print(proc.stderr[-1500:])
    results["checks"]["dbt_parse"] = {"passed": parsed}
    if not parsed:
        save_result("track_a", results)
        raise SystemExit("dbt parse に失敗。ここで停止して原因を仕様に照らして調べること。")

    manifest = json.loads((PROJECT / "target" / "manifest.json").read_text())

    # --- V3: 型情報を持たないディメンションの扱い ---
    step("V3. 型情報のないディメンションが dbt でどう分類されるか")
    dims: dict[str, str] = {}
    ents: dict[str, str] = {}
    measures: list = []
    for sm in manifest.get("semantic_models", {}).values():
        for d in sm.get("dimensions", []):
            dims[d["name"]] = d.get("type")
        for e in sm.get("entities", []):
            ents[e["name"]] = e.get("type")
        measures += [m["name"] for m in sm.get("measures", [])]

    print(f"  entities  : {ents}")
    print(f"  dimensions: {dims}")
    print(f"  measures  : {measures}")
    print()
    print("  OSI 側の宣言:")
    print("    order_id   -> primary_key, dimension.is_time=false")
    print("    status     -> dimension.is_time=false (文字列)")
    print("    amount     -> dimension.is_time=false (数値)")
    print("    ordered_at -> dimension.is_time=true")
    results["checks"]["V3_dimension_types"] = {
        "entities": ents, "dimensions": dims, "measures": measures,
    }

    # --- V4: メトリクスの集約式がどう写像されるか ---
    step("V4. メトリクスの写像")
    sem = json.loads((PROJECT / "target" / "semantic_manifest.json").read_text())
    metrics_info = []
    for m in sem.get("metrics", []):
        tp = m.get("type_params", {}) or {}
        info = {
            "name": m.get("name"),
            "type": m.get("type"),
            "measure": tp.get("measure"),
            "input_measures": tp.get("input_measures"),
            "expr": tp.get("expr"),
        }
        metrics_info.append(info)
        print(f"  {info}")
    results["checks"]["V4_metric_mapping"] = metrics_info

    # --- 実際に動くか ---
    step("V4-b. 取り込んだモデルで実際にクエリできるか")
    proc = dbt(["run"], PROJECT)
    ran = proc.returncode == 0
    print(("  dbt run: 成功" if ran else "  dbt run: 失敗"))
    if not ran:
        print(proc.stdout[-800:])
    results["checks"]["dbt_run"] = {"passed": ran}

    # --- V2: 公式スキーマより緩いか ---
    step("V2. 公式スキーマが禁じる未知キーを dbt が受理するか")
    bad = json.loads(doc.read_text())
    fields = bad["semantic_model"][0]["datasets"][0]["fields"]
    for f in fields:
        if f["name"] == "amount":
            # Field は additionalProperties: false。measure は存在しないキー。
            f["measure"] = {"aggregation": "sum"}
    bad_path = Path("/tmp/sales_invalid.json")
    bad_path.write_text(json.dumps(bad, ensure_ascii=False, indent=2))

    ok_bad, out_bad = validate(bad_path, "0.1.1")
    print(f"  公式バリデータ: {'通過(想定外)' if ok_bad else '拒否(想定どおり)'}")
    if not ok_bad:
        print("   ", out_bad.splitlines()[0] if out_bad else "")

    for f in OSI_DST.glob("*.json"):
        f.unlink()
    shutil.copy(bad_path, OSI_DST / "sales.json")
    proc = dbt(["parse"], PROJECT)
    dbt_accepted = proc.returncode == 0
    print(f"  dbt        : {'受理' if dbt_accepted else '拒否'}")
    results["checks"]["V2_leniency"] = {
        "official_validator_accepted": ok_bad,
        "dbt_accepted": dbt_accepted,
        "validator_output": out_bad,
    }

    # 後始末: 正しい文書に戻す
    for f in OSI_DST.glob("*.json"):
        f.unlink()
    shutil.copy(doc, OSI_DST / doc.name)

    # --- V5: 仕様外の前提 ---
    step("V5. 仕様にない前提の確認")
    yaml_probe = OSI_DST / "sales_as_yaml.yaml"
    yaml_probe.write_text("# dbt は .json のみ走査するため、これは無視されるはず\n")
    proc = dbt(["parse"], PROJECT)
    print(f"  OSI/ に .yaml を置いても parse は通るか: {'通る(=無視されている)' if proc.returncode == 0 else '落ちる'}")
    yaml_probe.unlink()
    results["checks"]["V5_yaml_ignored"] = {"parse_ok_with_yaml_present": proc.returncode == 0}

    save_result("track_a", results)
    hr("トラックA 完了")


if __name__ == "__main__":
    main()
