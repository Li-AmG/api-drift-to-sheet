# API Drift to Sheet

Catch API field changes before they silently break a spreadsheet export. Compare two saved JSON responses, see which fields were added, removed, changed type, or became optional, then export selected fields to CSV. Everything runs locally with Python's standard library; no API keys, account, or server are needed.

This is a small handoff and debugging tool for API integration work. It does **not** claim to sync Google Sheets, call a live API, or infer business-safe mappings automatically.

**中文简介：** 保存两次 API 返回的 JSON，运行 `check` 查看字段新增、删除、类型或是否必填的变化；用 `export` 按映射生成可在表格中打开的 CSV。全程本地处理，不上传客户数据。

## Try it

Requires Python 3.10+. From this repository:

```bash
python -m pip install -e .
api-drift-to-sheet check examples/before.json examples/after.json --root data.items
```

`check` returns exit code **2** when it finds a change, **0** when shapes match, and **1** for invalid input. Its default output is CSV, ready to open in Excel or Google Sheets. Use `--json` for machine-readable output or `--out report.csv` to write a new file. Existing files are never overwritten.

The example reports `amount` and `coupon` as added, and `total` as removed. Compare field types and presence counts before updating your downstream mapping.

To export the new response:

```bash
api-drift-to-sheet export examples/after.json examples/mapping.json orders.csv --root data.items
```

`mapping.json` maps a CSV heading to a dotted JSON field path:

```json
{"Order ID":"id","Customer":"customer.name","Amount":"amount","Status":"status"}
```

Arrays and empty objects become compact JSON in one CSV cell. Missing or `null` values become blank cells. A mapped field absent from **every** record is an error; a field absent from only some records produces blanks. Dotted keys in source JSON are rejected because they would be ambiguous with nested paths. UTF-8 CSV output uses standard quoting.

## Privacy and limits

The tool reads local files only and makes no network requests. Saved API responses may contain private customer data: use scrubbed samples before committing them or sharing reports. Type and presence checks describe the records supplied; they are not a full API schema or a guarantee of future compatibility. Exported cells starting with spreadsheet formula characters (`=`, `+`, `-`, `@`, including after whitespace) are prefixed with an apostrophe. Still review untrusted data before importing it elsewhere.

## Test

```bash
python -m unittest discover -s tests -v
```

## License

MIT
