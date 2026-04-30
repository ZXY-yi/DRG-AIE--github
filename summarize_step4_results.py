#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

import pandas as pd


def natural_key(path: Path):
    parts = re.split(r"(\d+)", path.stem)
    out = []
    for x in parts:
        if x.isdigit():
            out.append(int(x))
        else:
            out.append(x.lower())
    return out


def normalize_value(v):
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v).strip()


def build_field_order(records: List[Dict]) -> List[str]:
    if not records:
        return []
    ordered = []
    seen = set()
    for k in records[0].keys():
        if k not in seen:
            ordered.append(k)
            seen.add(k)
    for r in records[1:]:
        for k in r.keys():
            if k not in seen:
                ordered.append(k)
                seen.add(k)
    return ordered


def summarize(input_dir: Path, output_excel: Path):
    files = sorted(input_dir.glob("*_drg_fields.json"), key=natural_key)
    if not files:
        raise FileNotFoundError(f"No *_drg_fields.json found in: {input_dir}")

    rows = []
    for p in files:
        obj = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            continue
        rid = p.stem.split("_")[0]
        row = {"id": rid, "source_file": p.name}
        for k, v in obj.items():
            row[k] = normalize_value(v)
        rows.append(row)

    if not rows:
        raise RuntimeError(f"No valid JSON object records in: {input_dir}")

    field_order = build_field_order(rows)
    if "id" in field_order:
        field_order.remove("id")
    if "source_file" in field_order:
        field_order.remove("source_file")
    columns = ["id", "source_file"] + field_order
    df = pd.DataFrame(rows).reindex(columns=columns)

    # Field completeness stats
    stat_rows = []
    sample_n = len(df)
    for c in field_order:
        s = df[c].fillna("").astype(str).str.strip()
        non_empty = int((s != "").sum())
        empty = sample_n - non_empty
        unique_non_empty = int(s[s != ""].nunique())
        stat_rows.append(
            {
                "field": c,
                "non_empty_count": non_empty,
                "empty_count": empty,
                "non_empty_rate": round(non_empty / sample_n, 6),
                "unique_non_empty_count": unique_non_empty,
            }
        )
    stat_df = pd.DataFrame(stat_rows).sort_values(["non_empty_rate", "field"], ascending=[False, True])

    overview_df = pd.DataFrame(
        [
            {"metric": "样本数", "value": sample_n},
            {"metric": "字段数（不含id/source_file）", "value": len(field_order)},
            {"metric": "输入目录", "value": str(input_dir)},
            {"metric": "输出文件", "value": str(output_excel)},
        ]
    )

    output_excel.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        overview_df.to_excel(writer, sheet_name="Overview", index=False)
        df.to_excel(writer, sheet_name="Detail", index=False)
        stat_df.to_excel(writer, sheet_name="FieldStats", index=False)

    return output_excel, sample_n, len(field_order)


def main():
    script_dir = Path(__file__).resolve().parent
    default_input_dir = script_dir.parent / "原始未经扰动的数据跑出的结果step4"

    parser = argparse.ArgumentParser(description="Summarize step4 DRG field JSON results into one Excel workbook.")
    parser.add_argument(
        "--input-dir",
        default=str(default_input_dir),
        help="Directory containing *_drg_fields.json files.",
    )
    parser.add_argument(
        "--output-excel",
        default="",
        help="Output excel path. Default: <input-dir>/step4结果统计.xlsx",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"Input dir not found: {input_dir}")
    output_excel = Path(args.output_excel) if args.output_excel else (input_dir / "step4结果统计.xlsx")

    out, n_samples, n_fields = summarize(input_dir=input_dir, output_excel=output_excel)
    print(f"Saved: {out}")
    print(f"Samples: {n_samples}")
    print(f"Fields: {n_fields}")


if __name__ == "__main__":
    main()
