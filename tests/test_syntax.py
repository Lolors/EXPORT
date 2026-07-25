from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PythonSyntaxTests(unittest.TestCase):
    def test_all_python_files_parse(self) -> None:
        failures: list[str] = []
        for path in sorted(ROOT.rglob('*.py')):
            if any(part in {'.git', '.venv', 'venv'} for part in path.parts):
                continue
            try:
                ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            except SyntaxError as exc:
                failures.append(f'{path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}')
        self.assertEqual([], failures, '\n'.join(failures))


if __name__ == '__main__':
    unittest.main()
