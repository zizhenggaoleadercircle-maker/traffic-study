# tests

Automated tests for **traffic-study**. Run from the repository root after installing the package:

```bash
pip install -e .
python -m unittest discover -s tests -t .
```

The folder is named `tests` (plural) so `unittest` discovery does not clash with Python’s standard library `test` package (a top-level directory named `test` is not importable as a discovery root).
