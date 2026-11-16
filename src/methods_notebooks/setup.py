"""Portable input and credential setup; no data acquisition or method kernels."""

import getpass
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from urllib.parse import urlsplit
import zipfile

MAX_INPUT_BYTES = 512 * 1024 * 1024
INPUT_FILES = {"inputs.json", "manifest.json"}


def inspect_inputs(directory, expected_notebook=None):
    """Verify retained bytes before any API call; return metadata, never observations."""
    directory = Path(directory).expanduser().resolve()
    if any((directory / name).is_symlink() for name in INPUT_FILES):
        raise ValueError("Input files must be regular files, not symbolic links")
    manifest = json.loads((directory / "manifest.json").read_text())
    identifier = manifest.get("notebook_id")
    if not isinstance(identifier, str) or not identifier.startswith("NB-"):
        raise ValueError("Input manifest lacks a notebook identity")
    if expected_notebook is not None and identifier != expected_notebook:
        raise ValueError("Input bundle belongs to a different notebook")
    inputs = directory / "inputs.json"
    if inputs.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("Input bundle exceeds the size limit")
    payload = inputs.read_bytes()
    if hashlib.sha256(payload).hexdigest() != manifest.get("inputs_sha256"):
        raise ValueError("Private input checksum mismatch")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError("Notebook inputs must be a JSON object")
    return {"notebook_id": identifier, "inputs_sha256": manifest["inputs_sha256"],
            "input_names": sorted(parsed), "bytes": len(payload)}


def import_input_zip(payload, destination, expected_notebook=None):
    """Accept exactly two retained input files; reject ambiguous or unsafe archives."""
    if len(payload) > MAX_INPUT_BYTES:
        raise ValueError("Input bundle exceeds the size limit")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = archive.infolist()
        if len(members) != 2 or {x.filename for x in members} != INPUT_FILES:
            raise ValueError("Input ZIP must contain only inputs.json and manifest.json")
        if any(x.flag_bits & 1 or x.file_size > MAX_INPUT_BYTES or
               stat.S_IFMT(x.external_attr >> 16) not in (0, stat.S_IFREG)
               for x in members) or sum(x.file_size for x in members) > MAX_INPUT_BYTES:
            raise ValueError("Input ZIP contains an unsupported or oversized member")
        contents = {name: archive.read(name) for name in INPUT_FILES}
    # Validate identity and checksum before writing either file.
    manifest = json.loads(contents["manifest.json"])
    if expected_notebook is not None and manifest.get("notebook_id") != expected_notebook:
        raise ValueError("Input bundle belongs to a different notebook")
    if hashlib.sha256(contents["inputs.json"]).hexdigest() != manifest.get("inputs_sha256"):
        raise ValueError("Private input checksum mismatch")
    if not isinstance(json.loads(contents["inputs.json"]), dict):
        raise ValueError("Notebook inputs must be a JSON object")
    parent = Path(destination).expanduser().resolve()
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = Path(tempfile.mkdtemp(prefix="retained-", dir=parent))
    for name, content in contents.items():
        with (target / name).open("xb") as handle:
            handle.write(content)
        (target / name).chmod(0o600)
    inspect_inputs(target, expected_notebook)
    return target


def configure_notebook(notebook_id=None, *, require_key=True, prompt=True):
    """Select an existing private bundle and keep the credential out of notebook source."""
    selected = os.environ.get("EWB_NOTEBOOK_INPUT_DIR")
    if not selected:
        bundle = os.environ.get("EWB_NOTEBOOK_INPUT_ZIP")
        if not bundle and prompt:
            try:
                from google.colab import files
            except ImportError:
                bundle = input("Path to your private input ZIP (or input directory): ").strip()
            else:
                print("Select your private notebook input ZIP. It will be sent to this Google runtime.")
                uploads = files.upload()
                if len(uploads) != 1:
                    raise ValueError("Select exactly one private input ZIP")
                selected = import_input_zip(next(iter(uploads.values())),
                                            Path.cwd() / "data/raw/notebook-inputs", notebook_id)
                del uploads
        if bundle:
            path = Path(bundle).expanduser()
            selected = path if path.is_dir() else import_input_zip(
                path.read_bytes(), Path.cwd() / "data/raw/notebook-inputs", notebook_id)
    if not selected:
        raise ValueError("Set EWB_NOTEBOOK_INPUT_DIR or EWB_NOTEBOOK_INPUT_ZIP")
    checked = inspect_inputs(selected, notebook_id)
    os.environ["EWB_NOTEBOOK_INPUT_DIR"] = str(Path(selected).expanduser().resolve())
    output = Path(os.environ.get("EWB_NOTEBOOK_OUTPUT_DIR", "data/processed/notebook-results")).expanduser().resolve()
    if not any(output.parts[i:i+2] == ("data", "processed") for i in range(len(output.parts)-1)):
        raise ValueError("Notebook outputs must be stored beneath data/processed")
    if output == Path(selected).resolve() or output.is_relative_to(Path(selected).resolve()):
        raise ValueError("Keep result outputs separate from retained inputs")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.environ["EWB_NOTEBOOK_OUTPUT_DIR"] = str(output)
    if require_key:
        origin = os.environ.get("EWB_METHODS_URL", "https://api.sherandoresearch.com")
        url = urlsplit(origin)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in ("", "/")):
            raise ValueError("Use a plain HTTPS service origin")
        key = os.environ.get("EWB_METHODS_KEY")
        if not key and prompt:
            key = getpass.getpass("Your individual Workbench API key (hidden): ")
        if not key or not key.strip():
            raise ValueError("An individual Workbench API key is required")
        os.environ["EWB_METHODS_KEY"] = key
        os.environ["EWB_METHODS_URL"] = origin.rstrip("/")
        os.environ.pop("EWB_METHODS_ALLOW_LOOPBACK", None)
    return {**checked, "method_version": "1.43.0" if require_key else None,
            "mode": "private_api" if require_key else "offline_input_inspection",
            "scientific_acceptance": False}
