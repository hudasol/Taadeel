# Contributing

Taadeel is a research and navigation tool. It is not legal advice, and changes must keep that clear.

## Ground rules
1. No invented law text, citations, dates or amendments. Every provision shown links to its source with a retrieval date.
2. Synthetic data is labelled and stays out of real data views.
3. Respect each source's terms, robots.txt and rate limits. If a site blocks automated access, record the block in `docs/DATA_SOURCES.md` and stop. Do not work around it.
4. Do not commit law text from a source whose terms do not allow it.
5. Numbers in public documents come from `results/` through `python -m taadeel.report`. Do not type them by hand.
6. The engine files listed in `results/heldout_synthetic.json` are hash locked. A change to engine behaviour goes in a new versioned module with pre registered predictions and a new seed range.

## Development
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[api,dev,extract,store]"
pytest
```
Small commits, one logical change each, with a message that says what changed and why. Open a pull request for each milestone.
