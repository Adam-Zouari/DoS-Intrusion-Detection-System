# Live CICFlowMeter integration

This directory contains the tested Windows distribution of the project's CICFlowMeter fork. It publishes each completed flow directly to the IDS backend without an intermediate CSV file.

```text
Live packets
    -> CICFlowMeter completed bidirectional flow
    -> POST /api/flows
    -> frozen multiclass XGBoost pipeline
    -> SQLite and live dashboard
```

Detection occurs after a flow terminates or reaches its inactivity or maximum-duration timeout. It does not classify unfinished flows or block network traffic.

## Tested source

- Fork: <https://github.com/Adam-Zouari/CICFlowMeter>
- Source tag: [`ids-http-v1.0.0`](https://github.com/Adam-Zouari/CICFlowMeter/tree/ids-http-v1.0.0)
- Source commit: `803ad60cb7ddb28867c9a054494ae6a6853022a2`
- Bundled file: `CICFlowMeter-IDS-Windows-1.0.0.zip`
- SHA-256: `DF1A2F33A6338065DEAB48ECB8132B26588A49C2D5A2B49EC2BD182FC318D6CF`

The fork retains CICFlowMeter's MIT license, included as `CICFlowMeter-LICENSE.txt` and inside the distribution. The IDS repository's Apache license does not replace the upstream license.

## Requirements

- Windows
- Java available as `java.exe`
- Npcap with WinPcap-compatible API support
- The IDS Python package installed from this repository
- The backend running locally
- Administrator permissions when required by the local Npcap configuration

This release is tested and supported on Windows only.

## Run live capture

From the IDS repository root, start the backend in one PowerShell terminal:

```powershell
.\.venv\Scripts\Activate.ps1
$env:IDS_SOURCE_NAME = "Live CICFlowMeter"
ids-serve
```

Start the dashboard in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Then launch the bundled integration from an Administrator PowerShell terminal when Npcap requires elevated capture access:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File .\integrations\cicflowmeter\Start-CICFlowMeter-IDS.ps1
```

The launcher:

1. verifies that the backend exposes the expected 75-column flow contract;
2. extracts the versioned distribution under ignored `runtime-data/cicflowmeter-ids/` on first use;
3. sets `IDS_FLOW_ENDPOINT`; and
4. starts CICFlowMeter.

Use a different local backend endpoint with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File .\integrations\cicflowmeter\Start-CICFlowMeter-IDS.ps1 `
    -Endpoint http://127.0.0.1:9000/api/flows
```

Use `-Refresh` to replace the extracted runtime copy with the committed distribution.

After CICFlowMeter opens, select the active network interface and start capture. Each eligible completed flow is validated, classified, persisted, and inserted into the dashboard through Server-Sent Events without refreshing the page.

## Reproducible demonstration

The synthetic replay producer remains supported when live capture or the original dataset is unavailable:

```powershell
ids-generate-flows --count 100 --interval-ms 500
```

Both producers send the same flat flow contract to the same backend endpoint.
