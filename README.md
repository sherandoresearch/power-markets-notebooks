# Power Markets notebook helpers 0.1.0

Supports NB-01 and NB-11-CAPACITY on Python 3.12. Open the published notebook in Colab, connect a Python CPU runtime, and run all cells. The first cell verifies and installs this versioned helper archive and its pinned dependencies. Start with a fresh runtime; if dependencies have already been imported at different versions, restart the session first.

NB-01 includes the existing equal-reactance triangle manifest and published teaching assumptions. No new synthetic data is generated.

NB-11-CAPACITY requires the separately supplied `nb-11-capacity-inputs-v1.zip`. Upload only through its notebook upload cell. The archive is not in this release or repository. Uploading transfers it to your Google Colab runtime; it does not publish it to GitHub. Do not share a saved notebook containing new sensitive outputs. Previously reviewed reader results remain in the downloadable notebook.

For local Jupyter, set BOOK_LABS_INPUT_ZIP to the private archive path before running NB-11-CAPACITY. A release download is still required. BOOK_LABS_RELEASE_ZIP can point to an offline copy of the exact release ZIP; checksum verification remains mandatory. No API keys or EWB access are needed.

The capacity calculation preserves the reviewed interval-containment and vintage checks. Hashes bind uploads to the retained capture bytes; they do not independently validate the upstream source. The public input contract contains hashes and filenames only.

## Open the notebooks

- [NB-01 in Colab](https://colab.research.google.com/github/sherandoresearch/power-markets-notebooks/blob/notebooks-v0.1.1/reports/book-labs/published/NB-01.ipynb)
- [NB-11-CAPACITY in Colab](https://colab.research.google.com/github/sherandoresearch/power-markets-notebooks/blob/notebooks-v0.1.1/reports/book-labs/published/NB-11-CAPACITY.ipynb)
- [Series notebook contents](https://sherandoresearch.github.io/power-markets-series/notebooks.html)

This is a minimal public distribution. The authoring repository and raw observed inputs remain private.

Notebook documentation revision 0.1.1 adds direct reading links and explains the Volume V context of the ENTSOG capacity example. The verified helper release remains 0.1.0; code, data, and reviewed outputs are unchanged.
