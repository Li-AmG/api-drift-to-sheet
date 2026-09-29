import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from api_drift_to_sheet.cli import main
from api_drift_to_sheet.core import DataError, compare, export_csv, flatten, load_records


class DriftTests(unittest.TestCase):
    def test_detects_added_removed_type_and_optional(self):
        before = [{"id": 1, "customer": {"name": "Ada"}, "old": "x", "optional": 1},
                  {"id": 2, "customer": {"name": "Lin"}, "old": "y", "optional": 2}]
        after = [{"id": "1", "customer": {"name": "Ada"}, "new": True, "optional": 1},
                 {"id": "2", "customer": {"name": "Lin"}, "new": False}]
        changes = {item["field"]: item["change"] for item in compare(before, after)}
        self.assertEqual(changes, {"id": "type_changed", "new": "added", "old": "removed", "optional": "became_optional"})

    def test_csv_quotes_values_and_preserves_unicode(self):
        text = export_csv([{"id": 1, "name": "李, 明", "tags": ["a", "b"]}],
                          {"ID": "id", "Name": "name", "Tags": "tags"})
        self.assertEqual(list(csv.DictReader(io.StringIO(text))),
                         [{"ID": "1", "Name": "李, 明", "Tags": '["a","b"]'}])

    def test_absent_mapped_field_rejected(self):
        with self.assertRaises(DataError):
            export_csv([{"id": 1}], {"Missing": "customer.name"})

    def test_spreadsheet_formula_is_neutralized(self):
        text = export_csv([{"name": "  =SUM(1,2)", "code": "-cmd", "balance": -12}],
                          {"Name": "name", "Code": "code", "Balance": "balance"})
        self.assertEqual(list(csv.DictReader(io.StringIO(text))),
                         [{"Name": "'  =SUM(1,2)", "Code": "'-cmd", "Balance": "-12"}])

    def test_formula_column_name_is_rejected(self):
        with self.assertRaises(DataError):
            export_csv([{"id": 1}], {"=HYPERLINK(\"x\")": "id"})

    def test_ambiguous_dotted_key_rejected(self):
        with self.assertRaises(DataError):
            flatten({"customer.name": "Ada"})

    def test_nested_root_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source = folder / "sample.json"
            source.write_text(json.dumps({"data": {"items": [{"id": 1}]}}), encoding="utf-8")
            mapping = folder / "map.json"
            mapping.write_text('{"ID":"id"}', encoding="utf-8")
            target = folder / "output.csv"
            self.assertEqual(len(load_records(source, "data.items")), 1)
            self.assertEqual(main(["export", str(source), str(mapping), str(target), "--root", "data.items"]), 0)
            self.assertEqual(main(["export", str(source), str(mapping), str(target), "--root", "data.items"]), 1)

    def test_check_exit_code_distinguishes_drift_from_match(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            before = folder / "before.json"
            after = folder / "after.json"
            before.write_text('{"id":1}', encoding="utf-8")
            after.write_text('{"id":"1"}', encoding="utf-8")
            self.assertEqual(main(["check", str(before), str(before)]), 0)
            self.assertEqual(main(["check", str(before), str(after), "--json"]), 2)


if __name__ == "__main__":
    unittest.main()
