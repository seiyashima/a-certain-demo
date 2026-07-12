"""Federated search backend package.

This package also re-exports the legacy ``create_app`` factory from the
repository root ``app.py`` so pre-existing gateway tests keep working after
introducing the ``app/`` package.
"""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_legacy_create_app():
	legacy_path = Path(__file__).resolve().parents[1] / "app.py"
	spec = spec_from_file_location("legacy_app_module", legacy_path)
	if spec is None or spec.loader is None:
		raise ImportError("could not load legacy app module")
	module = module_from_spec(spec)
	spec.loader.exec_module(module)
	return module.create_app


create_app = _load_legacy_create_app()

