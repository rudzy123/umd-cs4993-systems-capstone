# Northstar worker

Separate OS process that polls PostgreSQL, claims one job at a time, and executes it.

Install the backend package first:

```bash
pip install -e "../backend[dev]" -e ".[dev]"
python -m northstar_worker
```
