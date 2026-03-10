#!/usr/bin/env python3
"""台股財報統整分析腳本。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

INCOME_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
BALANCE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"
CASHFLOW_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap06_L"


@dataclass
class CompanyFinancial:
    stock_id: str
    name: str = ""
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    operating_cashflow: Optional[float] = None

    @property
    def net_margin(self) -> Optional[float]:
        if self.revenue in (None, 0) or self.net_income is None:
            return None
        return self.net_income / self.revenue

    @property
    def debt_ratio(self) -> Optional[float]:
        if self.total_assets in (None, 0) or self.total_liabilities is None:
            return None
        return self.total_liabilities / self.total_assets

    @property
    def roa(self) -> Optional[float]:
        if self.total_assets in (None, 0) or self.net_income is None:
            return None
        return self.net_income / self.total_assets

    @property
    def ocf_to_income(self) -> Optional[float]:
        if self.net_income in (None, 0) or self.operating_cashflow is None:
            return None
        return self.operating_cashflow / self.net_income


def parse_number(value: str) -> Optional[float]:
    if value is None:
        return None
    cleaned = str(value).replace(",", "").strip()
    if cleaned in {"", "--", "N/A", "nan", "None"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def pick(row: Dict[str, str], candidates: Iterable[str]) -> Optional[str]:
    for key in candidates:
        if key in row and str(row[key]).strip() != "":
            return row[key]
    return None


def read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fetch_json(url: str) -> List[Dict[str, str]]:
    with urllib.request.urlopen(url, timeout=30) as resp:
        payload = resp.read().decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError(f"Unexpected payload type from {url}: {type(data)}")
    return data


def write_csv(path: str, rows: List[CompanyFinancial]) -> None:
    fields = [
        "stock_id",
        "name",
        "revenue",
        "net_income",
        "total_assets",
        "total_liabilities",
        "operating_cashflow",
        "net_margin",
        "debt_ratio",
        "roa",
        "ocf_to_income",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "stock_id": r.stock_id,
                    "name": r.name,
                    "revenue": r.revenue,
                    "net_income": r.net_income,
                    "total_assets": r.total_assets,
                    "total_liabilities": r.total_liabilities,
                    "operating_cashflow": r.operating_cashflow,
                    "net_margin": r.net_margin,
                    "debt_ratio": r.debt_ratio,
                    "roa": r.roa,
                    "ocf_to_income": r.ocf_to_income,
                }
            )


def fmt_pct(v: Optional[float]) -> str:
    if v is None or math.isnan(v):
        return "N/A"
    return f"{v * 100:.2f}%"


def fmt(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    return f"{v:,.0f}"


def rank_top(rows: List[CompanyFinancial], key: str, n: int = 10, reverse: bool = True) -> List[CompanyFinancial]:
    valid = [r for r in rows if getattr(r, key) is not None]
    valid.sort(key=lambda r: getattr(r, key), reverse=reverse)
    return valid[:n]


def build_summary(path: str, rows: List[CompanyFinancial]) -> None:
    margins = [r.net_margin for r in rows if r.net_margin is not None]
    debts = [r.debt_ratio for r in rows if r.debt_ratio is not None]
    roas = [r.roa for r in rows if r.roa is not None]

    with open(path, "w", encoding="utf-8") as f:
        f.write("# 台股財報自動分析摘要\n\n")
        f.write(f"- 納入公司數：{len(rows)}\n")
        f.write(f"- 具淨利率資料：{len(margins)}\n")
        f.write(f"- 具負債比資料：{len(debts)}\n")
        f.write(f"- 具 ROA 資料：{len(roas)}\n\n")

        if margins:
            f.write(f"- 全體淨利率中位數：{fmt_pct(statistics.median(margins))}\n")
        if debts:
            f.write(f"- 全體負債比中位數：{fmt_pct(statistics.median(debts))}\n")
        if roas:
            f.write(f"- 全體 ROA 中位數：{fmt_pct(statistics.median(roas))}\n")
        f.write("\n")

        f.write("## 淨利率前 10 名\n")
        for c in rank_top(rows, "net_margin"):
            f.write(f"- {c.stock_id} {c.name}：淨利率 {fmt_pct(c.net_margin)}，營收 {fmt(c.revenue)}，淨利 {fmt(c.net_income)}\n")

        f.write("\n## ROA 前 10 名\n")
        for c in rank_top(rows, "roa"):
            f.write(f"- {c.stock_id} {c.name}：ROA {fmt_pct(c.roa)}，總資產 {fmt(c.total_assets)}\n")

        f.write("\n## 負債比前 10 名（槓桿較高）\n")
        for c in rank_top(rows, "debt_ratio"):
            f.write(f"- {c.stock_id} {c.name}：負債比 {fmt_pct(c.debt_ratio)}\n")


def merge_financials(
    income_rows: List[Dict[str, str]],
    balance_rows: List[Dict[str, str]],
    cashflow_rows: List[Dict[str, str]],
) -> List[CompanyFinancial]:
    data: Dict[str, CompanyFinancial] = {}

    for row in income_rows:
        sid = pick(row, ["公司代號", "stock_id", "公司代碼", "code"])
        if not sid:
            continue
        c = data.setdefault(sid, CompanyFinancial(stock_id=sid))
        c.name = c.name or (pick(row, ["公司名稱", "name"]) or "")
        c.revenue = c.revenue if c.revenue is not None else parse_number(pick(row, ["營業收入", "revenue"]))
        c.net_income = c.net_income if c.net_income is not None else parse_number(pick(row, ["本期淨利（淨損）", "本期稅後淨利（淨損）", "net_income"]))

    for row in balance_rows:
        sid = pick(row, ["公司代號", "stock_id", "公司代碼", "code"])
        if not sid:
            continue
        c = data.setdefault(sid, CompanyFinancial(stock_id=sid))
        c.name = c.name or (pick(row, ["公司名稱", "name"]) or "")
        c.total_assets = c.total_assets if c.total_assets is not None else parse_number(pick(row, ["資產總額", "total_assets"]))
        c.total_liabilities = c.total_liabilities if c.total_liabilities is not None else parse_number(
            pick(row, ["負債總額", "total_liabilities"])
        )

    for row in cashflow_rows:
        sid = pick(row, ["公司代號", "stock_id", "公司代碼", "code"])
        if not sid:
            continue
        c = data.setdefault(sid, CompanyFinancial(stock_id=sid))
        c.name = c.name or (pick(row, ["公司名稱", "name"]) or "")
        c.operating_cashflow = c.operating_cashflow if c.operating_cashflow is not None else parse_number(
            pick(row, ["營業活動之淨現金流入（流出）", "營業活動淨現金流量", "operating_cashflow"])
        )

    return sorted(data.values(), key=lambda x: x.stock_id)


def main() -> None:
    p = argparse.ArgumentParser(description="統整台股財報並輸出分析")
    p.add_argument("--fetch", action="store_true", help="從 TWSE API 下載資料")
    p.add_argument("--income-csv", default="")
    p.add_argument("--balance-csv", default="")
    p.add_argument("--cashflow-csv", default="")
    p.add_argument("--output-dir", default="output")
    args = p.parse_args()

    if args.fetch:
        try:
            income_rows = fetch_json(INCOME_URL)
            balance_rows = fetch_json(BALANCE_URL)
            cashflow_rows = fetch_json(CASHFLOW_URL)
        except (urllib.error.URLError, ValueError) as e:
            raise SystemExit(f"資料下載失敗：{e}")
    else:
        if not (args.income_csv and args.balance_csv and args.cashflow_csv):
            raise SystemExit("離線模式需提供 --income-csv --balance-csv --cashflow-csv")
        income_rows = read_csv(args.income_csv)
        balance_rows = read_csv(args.balance_csv)
        cashflow_rows = read_csv(args.cashflow_csv)

    rows = merge_financials(income_rows, balance_rows, cashflow_rows)

    os.makedirs(args.output_dir, exist_ok=True)
    merged_path = os.path.join(args.output_dir, "merged_financials.csv")
    summary_path = os.path.join(args.output_dir, "analysis_summary.md")
    write_csv(merged_path, rows)
    build_summary(summary_path, rows)

    print(f"分析完成，共 {len(rows)} 家公司")
    print(f"輸出：{merged_path}")
    print(f"輸出：{summary_path}")


if __name__ == "__main__":
    main()
