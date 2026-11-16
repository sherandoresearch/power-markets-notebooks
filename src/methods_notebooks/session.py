"""Explicit remote execution with local, immutable private receipts and results."""

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import uuid

from ewb_methods_client import MethodsClient, MethodsError


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def read_saved(path):
    """Explicit offline reader; never invoked as a fallback for a failed request."""
    response = json.loads(Path(path).read_text())
    if (
        digest({k: response[k] for k in ("result", "diagnostics")})
        != response["receipt"]["result_sha256"]
    ):
        raise ValueError("Saved result differs from its execution receipt")
    return response


def setup_plot():
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.facecolor": "#2E3440",
            "axes.facecolor": "#2E3440",
            "text.color": "#ECEFF4",
            "axes.labelcolor": "#ECEFF4",
            "xtick.color": "#D8DEE9",
            "ytick.color": "#D8DEE9",
            "axes.edgecolor": "#4C566A",
            "grid.color": "#4C566A",
            "figure.figsize": (9, 4),
            "figure.dpi": 120,
            "savefig.facecolor": "#2E3440",
        }
    )
    return plt


class Session:
    def __init__(self, notebook_id, version="1.15.0"):
        self.notebook_id, self.version = notebook_id, version
        source = Path(os.environ["EWB_NOTEBOOK_INPUT_DIR"]).resolve()
        manifest = json.loads((source / "manifest.json").read_text())
        if manifest["notebook_id"] != notebook_id:
            raise ValueError("Input bundle belongs to a different notebook")
        if (
            hashlib.sha256((source / "inputs.json").read_bytes()).hexdigest()
            != manifest["inputs_sha256"]
        ):
            raise ValueError("Private input checksum mismatch")
        self.inputs = json.loads((source / "inputs.json").read_text())
        self.input_manifest = manifest
        self.run_id = uuid.uuid4().hex
        self.output = (
            Path(os.environ["EWB_NOTEBOOK_OUTPUT_DIR"]).resolve() / self.run_id
        )
        self.output.mkdir(parents=True, exist_ok=False, mode=0o700)
        self.client = MethodsClient(
            os.environ["EWB_METHODS_URL"],
            os.environ["EWB_METHODS_KEY"],
            allow_loopback_http=os.getenv("EWB_METHODS_ALLOW_LOOPBACK") == "1",
        )
        self.calls = []

    def execute(self, operation, request):
        record = dict(
            operation=operation, version=self.version, request_sha256=digest(request)
        )
        try:
            result = self.client.execute(operation, self.version, request)
        except MethodsError as exc:
            record.update(status="refused", error=str(exc))
            self.calls.append(record)
            self._save()
            raise
        receipt = result["receipt"]
        if (
            result["status"] != "succeeded"
            or receipt["method_id"] != operation
            or receipt["method_version"] != self.version
        ):
            raise ValueError(
                "Service response does not match the requested operation/version"
            )
        if (
            digest({k: result[k] for k in ("result", "diagnostics")})
            != receipt["result_sha256"]
        ):
            raise ValueError("Result checksum mismatch")
        record.update(
            status="succeeded",
            receipt=receipt,
            result_file=f"result-{len(self.calls):03d}.json",
        )
        with (self.output / record["result_file"]).open("x") as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
        self.calls.append(record)
        self._save()
        return result

    def _save(self):
        # Progress is mutable only within this fresh local run. Final receipt is not.
        (self.output / "progress.json").write_text(
            json.dumps(self.calls, indent=2) + "\n"
        )

    def finish(self, checks, parameters=None):
        report = dict(
            run_id=self.run_id,
            notebook_id=self.notebook_id,
            distribution="PRIVATE",
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            scientific_acceptance=False,
            input_manifest=self.input_manifest,
            checks=checks,
            parameters=parameters or {},
            calls=self.calls,
            environment={
                name: importlib.metadata.version(name)
                for name in ("numpy", "matplotlib", "httpx")
            },
        )
        with (self.output / "receipt.json").open("x") as handle:
            json.dump(report, handle, indent=2, allow_nan=False)
        self.client.close()
        return dict(
            run_id=self.run_id,
            notebook=self.notebook_id,
            output=str(self.output),
            checks=checks,
            distribution="PRIVATE",
            scientific_acceptance=False,
        )
