from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_ROOT = PROJECT_ROOT / "integrations" / "cicflowmeter"
ARCHIVE = INTEGRATION_ROOT / "CICFlowMeter-IDS-Windows-1.0.0.zip"
EXPECTED_SHA256 = "df1a2f33a6338065deab48ecb8132b26588a49c2d5a2b49ec2bd182fc318d6cf"
ARCHIVE_ROOT = "CICFlowMeter-4.0-ids1/"


def test_committed_windows_distribution_is_the_tested_build() -> None:
    digest = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    assert digest == EXPECTED_SHA256

    with zipfile.ZipFile(ARCHIVE) as bundle:
        names = set(bundle.namelist())

    assert ARCHIVE_ROOT + "bin/CICFlowMeter.bat" in names
    assert ARCHIVE_ROOT + "lib/native/jnetpcap.dll" in names
    assert ARCHIVE_ROOT + "lib/native/jnetpcap-pcap100.dll" in names
    assert ARCHIVE_ROOT + "LICENSE.txt" in names
    assert ARCHIVE_ROOT + "README-IDS.md" in names
    assert ARCHIVE_ROOT + "lib/log4j-core-2.25.4.jar" in names
    assert not any("log4j-core-2.11.0" in name for name in names)


def test_launcher_and_release_metadata_match_the_bundle() -> None:
    launcher = (INTEGRATION_ROOT / "Start-CICFlowMeter-IDS.ps1").read_text(
        encoding="utf-8"
    )
    readme = (INTEGRATION_ROOT / "README.md").read_text(encoding="utf-8")

    assert "CICFlowMeter-IDS-Windows-1.0.0.zip" in launcher
    assert "http://127.0.0.1:8000/api/flows" in launcher
    assert "expected_input_columns.Count -ne 75" in launcher
    assert "ids-http-v1.0.0" in readme
    assert EXPECTED_SHA256.upper() in readme
    assert (INTEGRATION_ROOT / "CICFlowMeter-LICENSE.txt").is_file()
