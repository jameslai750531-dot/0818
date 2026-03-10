# 台股財報統整與分析工具

此專案提供一個**可批次處理台股全市場股票**的 Python 腳本，會把損益表、資產負債表、現金流量表合併後，計算關鍵比率並輸出總覽報表。

> 在目前執行環境中，外網被封鎖（HTTP tunnel 403），無法即時抓取 TWSE 開放資料；但腳本已支援在可連網環境自動抓取，或使用離線 CSV 分析。

## 功能
- 合併三大報表（損益／資產負債／現金流）
- 以股票代號為主鍵做彙整
- 計算財務指標：
  - 淨利率
  - 負債比率
  - ROA（資產報酬率）
  - OCF/淨利（現金含金量）
- 產出：
  - `merged_financials.csv`（公司層級資料）
  - `analysis_summary.md`（文字分析）

## 使用方式

### 1) 可連網環境（自動抓取）
```bash
python analyze_tw_stock_financials.py \
  --fetch \
  --output-dir output
```

### 2) 離線模式（使用既有 CSV）
```bash
python analyze_tw_stock_financials.py \
  --income-csv sample_data/income.csv \
  --balance-csv sample_data/balance.csv \
  --cashflow-csv sample_data/cashflow.csv \
  --output-dir output
```

## TWSE API 預設端點
- 損益表：`https://openapi.twse.com.tw/v1/opendata/t187ap05_L`
- 資產負債表：`https://openapi.twse.com.tw/v1/opendata/t187ap04_L`
- 現金流量表：`https://openapi.twse.com.tw/v1/opendata/t187ap06_L`

若欄位命名有差異，可在腳本中的欄位對應函式調整。
