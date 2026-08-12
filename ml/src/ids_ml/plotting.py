"""Shared non-interactive plotting backend for experiment artifacts."""

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt  # noqa: E402

__all__ = ["plt"]
