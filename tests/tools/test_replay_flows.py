from __future__ import annotations

from pathlib import Path

import pyarrow as arrow
import pyarrow.parquet as parquet

from ids_tools.replay_flows import iter_replay_rows

from tests.backend.test_contracts import valid_payload


def test_generator_keeps_ground_truth_private(tmp_path: Path) -> None:
    first = valid_payload()
    first["Label"] = "BENIGN"
    second = valid_payload()
    second["Flow ID"] = "second"
    second["Label"] = "DoS Hulk"
    path = tmp_path / "flows.parquet"
    parquet.write_table(arrow.Table.from_pylist([first, second]), path)

    rows = list(iter_replay_rows(path, labels={"DoS Hulk"}))

    assert len(rows) == 1
    payload, expected = rows[0]
    assert expected == "DoS Hulk"
    assert payload["Flow ID"] == "second"
    assert "Label" not in payload
    assert "ClassLabel" not in payload
