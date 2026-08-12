# CIC-IDS-2017 dataset and feature reference

This document is the authoritative reference for dataset provenance, flow terminology, and feature meanings. The [data-exploration notebook](notebooks/01_data_exploration.ipynb) contains the observed data-quality results, cleaning counts, label distributions, and generated cleaned dataset.

## Dataset source

The project uses the [official CIC-IDS-2017 dataset](https://www.unb.ca/cic/datasets/ids-2017.html) produced by the Canadian Institute for Cybersecurity at the University of New Brunswick. The dataset is not distributed by this repository and is not covered by this project's Apache 2.0 license.

Use the citation requested by the dataset publisher:

> Iman Sharafaldin, Arash Habibi Lashkari, and Ali A. Ghorbani. "Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization." *Proceedings of the 4th International Conference on Information Systems Security and Privacy (ICISSP)*, 2018.

The original flow CSV exports were concatenated into one uncleaned local file:

```text
ml/data/raw/cicids2017_merged.csv
```

Merging the exports does not alter the individual flow records and is suitable here because the model consumes flow rows rather than separate files. The raw file is immutable and ignored by Git.

The `ClassLabel` column was project-generated and was removed from the raw CSV. The official `Label` column is the only target used by the current workflow.

## CICFlowMeter flow direction

CICFlowMeter creates **bidirectional flows**. The first observed packet establishes the **forward** direction (`Src IP` -> `Dst IP`); packets travelling in the reverse direction are **backward**.

Forward does not mean attacker -> victim, and backward does not mean victim -> attacker. Those security roles must be inferred separately from the scenario, timestamp, addresses, and label.

Time and inter-arrival-time fields are measured in microseconds, byte and length fields are measured in bytes, rate fields are per second, and count fields are dimensionless.

The definitions below follow the [official CICFlowMeter feature list](https://github.com/ahlashkari/CICFlowMeter/blob/master/ReadMe.txt), the [UNB CICFlowMeter overview](https://www.unb.ca/cic/research/applications.html), and the published [`BasicFlow` implementation](https://github.com/ahlashkari/CICFlowMeter/blob/master/src/main/java/cic/cs/unb/ca/jnetpcap/BasicFlow.java). Dataset column spellings are preserved. Some behavior can vary between CICFlowMeter versions and is marked explicitly.

## What determines a flow?

Packets are grouped primarily by the network **5-tuple**:

1. Source IP address
2. Destination IP address
3. Source port
4. Destination port
5. IP protocol, such as TCP or UDP

CICFlowMeter treats the reverse 5-tuple as the backward direction of the same bidirectional flow. For example, `192.168.10.5:51000 -> 104.16.10.20:443 (TCP)` and its reply belong to the same flow. The first observed packet decides which direction is called forward.

Time also separates flows. TCP flows normally end on connection termination, such as FIN or RST, while UDP and inactive or long-running traffic are separated using configured timeouts. Reuse of the same 5-tuple after a flow ends can therefore produce a new flow.

> **Flow = bidirectional 5-tuple + its time/session boundary**

Attacker and victim roles and the benign or attack label do not determine flow membership. They are interpretations assigned after packet grouping.

## Feature dictionary

### Flow identity, endpoints, and target

| Column | Meaning |
|---|---|
| `Flow ID` | Identifier constructed from the flow endpoints, ports, and protocol. It identifies a flow inside the generated data but should not be assumed globally unique across captures. |
| `Src IP` | Source IP address of the first observed packet; establishes the forward-flow origin but is not necessarily the attacker. |
| `Src Port` | Transport-layer source port of the forward origin. A value of zero can occur when a port is not applicable. |
| `Dst IP` | Destination IP address of the first observed packet; establishes the forward-flow destination but is not necessarily the victim. |
| `Dst Port` | Transport-layer destination port. A value of zero can occur when a port is not applicable. |
| `Protocol` | Numeric IP protocol identifier. The observed cleaned values are `0` (HOPOPT), `6` (TCP), and `17` (UDP). The stored numeric values remain unchanged; model pipelines handle their encoding. |
| `Timestamp` | Recorded start date and time of the flow. |
| `Label` | Ground-truth benign or attack class. This is the supervised target and must never be included in model features. |

### Duration, traffic volume, and directional payload lengths

In ordinary language, **length** and **size** both mean a number of bytes. CICFlowMeter's legacy names are not consistently distinct: the published source populates packet `Length` and average `Size` statistics from the packet payload-byte count, while `Header Length` separately measures header bytes. These fields should not be interpreted as complete on-the-wire frame sizes.

| Column | Meaning |
|---|---|
| `Flow Duration` | Elapsed time from the first to the last packet in the flow, in microseconds. |
| `Total Fwd Packet` | Number of packets travelling in the forward direction. |
| `Total Bwd packets` | Number of packets travelling in the backward direction. |
| `Total Length of Fwd Packet` | Sum of forward packet payload lengths, in bytes. It excludes separately counted header bytes. |
| `Total Length of Bwd Packet` | Sum of backward packet payload lengths, in bytes. It excludes separately counted header bytes. |
| `Fwd Packet Length Max` | Maximum forward packet payload length, in bytes. |
| `Fwd Packet Length Min` | Minimum forward packet payload length, in bytes. |
| `Fwd Packet Length Mean` | Mean forward packet payload length, in bytes. |
| `Fwd Packet Length Std` | Standard deviation of forward packet payload lengths, in bytes. |
| `Bwd Packet Length Max` | Maximum backward packet payload length, in bytes. |
| `Bwd Packet Length Min` | Minimum backward packet payload length, in bytes. |
| `Bwd Packet Length Mean` | Mean backward packet payload length, in bytes. |
| `Bwd Packet Length Std` | Standard deviation of backward packet payload lengths, in bytes. |

### Flow rates and inter-arrival times

`IAT` means **inter-arrival time**: the elapsed time between consecutive packets.

| Column | Meaning |
|---|---|
| `Flow Bytes/s` | Total forward and backward payload bytes divided by flow duration, expressed as bytes per second. |
| `Flow Packets/s` | Total flow packets divided by flow duration, expressed as packets per second. |
| `Flow IAT Mean` | Mean IAT across consecutive packets in the complete bidirectional flow, in microseconds. |
| `Flow IAT Std` | Standard deviation of complete-flow IATs, in microseconds. |
| `Flow IAT Max` | Maximum complete-flow IAT, in microseconds. |
| `Flow IAT Min` | Minimum complete-flow IAT, in microseconds. |
| `Fwd IAT Total` | Sum of IATs between consecutive forward packets, in microseconds. |
| `Fwd IAT Mean` | Mean forward-packet IAT, in microseconds. |
| `Fwd IAT Std` | Standard deviation of forward-packet IATs, in microseconds. |
| `Fwd IAT Max` | Maximum forward-packet IAT, in microseconds. |
| `Fwd IAT Min` | Minimum forward-packet IAT, in microseconds. |
| `Bwd IAT Total` | Sum of IATs between consecutive backward packets, in microseconds. |
| `Bwd IAT Mean` | Mean backward-packet IAT, in microseconds. |
| `Bwd IAT Std` | Standard deviation of backward-packet IATs, in microseconds. |
| `Bwd IAT Max` | Maximum backward-packet IAT, in microseconds. |
| `Bwd IAT Min` | Minimum backward-packet IAT, in microseconds. |

### Directional flags, headers, payload statistics, and TCP flags

`Fwd/Bwd PSH Flags` and `Fwd/Bwd URG Flags` are directional counters included by CICFlowMeter's legacy feature schema. There is no TCP rule requiring only PSH and URG to be directional; the tool simply does not export equivalent directional counters for every flag. The later `... Flag Count` columns count flags across the complete bidirectional flow.

A directional PSH or URG value of zero does not mean the flow is UDP. It means CICFlowMeter counted no such flag in that direction. UDP flows also receive zero because TCP flags do not apply, but many TCP flows legitimately contain no PSH or URG flags.

| Column | Meaning |
|---|---|
| `Fwd PSH Flags` | Number of forward packets with the TCP PSH flag set. |
| `Bwd PSH Flags` | Number of backward packets with the TCP PSH flag set. |
| `Fwd URG Flags` | Number of forward packets with the TCP URG flag set. |
| `Bwd URG Flags` | Number of backward packets with the TCP URG flag set. |
| `Fwd Header Length` | Total bytes used by packet headers in the forward direction. |
| `Bwd Header Length` | Total bytes used by packet headers in the backward direction. |
| `Fwd Packets/s` | Forward packets per second. |
| `Bwd Packets/s` | Backward packets per second. |
| `Packet Length Min` | Minimum packet payload length across both directions, in bytes. |
| `Packet Length Max` | Maximum packet payload length across both directions, in bytes. |
| `Packet Length Mean` | Mean packet payload length across both directions, in bytes. |
| `Packet Length Std` | Standard deviation of packet payload lengths across both directions, in bytes. |
| `Packet Length Variance` | Variance of packet payload lengths across both directions, in squared bytes. |
| `FIN Flag Count` | Number of flow packets with the TCP FIN flag set. |
| `SYN Flag Count` | Number of flow packets with the TCP SYN flag set. |
| `RST Flag Count` | Number of flow packets with the TCP RST flag set. |
| `PSH Flag Count` | Number of flow packets with the TCP PSH flag set across both directions. |
| `ACK Flag Count` | Number of flow packets with the TCP ACK flag set. |
| `URG Flag Count` | Number of flow packets with the TCP URG flag set across both directions. |
| `CWR Flag Count` | Number of flow packets with the TCP CWR flag set. |
| `ECE Flag Count` | Number of flow packets with the TCP ECE flag set. |
| `Down/Up Ratio` | Backward packet count divided by forward packet count. In the published implementation the division uses integer division, so the fractional part is truncated. It is zero when no forward packet exists. |
| `Average Packet Size` | Average payload bytes per packet across the flow. Despite the word `Size`, it is derived from the same payload-length statistics. |
| `Fwd Segment Size Avg` | Average forward payload bytes per packet. In the published implementation this is mathematically the same quantity as `Fwd Packet Length Mean`. |
| `Bwd Segment Size Avg` | Average backward payload bytes per packet. In the published implementation this is mathematically the same quantity as `Bwd Packet Length Mean`. |

### Bulk transfers, subflows, and TCP window or segment features

These are CICFlowMeter-specific summaries rather than fields taken directly from a single network packet.

#### Bulk

A **bulk** is a sustained run of payload-carrying packets travelling in one direction. In the published implementation:

- only packets containing payload participate;
- packets must travel in the same direction;
- a candidate becomes a bulk when it reaches at least four packets;
- a gap longer than one second breaks the candidate bulk; and
- traffic in the opposite direction can end or reset the candidate.

For example, four forward payload packets at `0.0 s`, `0.1 s`, `0.2 s`, and `0.3 s` form a forward bulk. Only three such packets do not form a bulk, and a gap greater than one second starts a new candidate. A zero bulk feature normally means no sequence satisfied these rules, not that the value is missing.

#### Subflow

A **subflow** is an activity chunk inside an existing flow. A connection may send a burst, pause for several seconds, and then send another burst while retaining the same 5-tuple. It remains one network flow, but CICFlowMeter can divide its activity into separate subflows. In the published implementation, an inactivity gap greater than one second creates a new subflow boundary.

```text
One bidirectional flow
|-- Subflow 1: first packet burst
`-- Subflow 2: second packet burst after an inactivity gap
```

The subflow features summarize average forward or backward packets and payload bytes per detected chunk. A subflow is not a new TCP connection. If a flow contains only one detected chunk, its subflow values can equal its whole-flow totals.

#### TCP receive window

The TCP **receive window** is a flow-control value advertised by an endpoint. It tells the peer approximately how much additional unacknowledged data the endpoint can currently receive. For example, an advertised window of `65,535` reports capacity for that amount of data; it does not mean 65,535 bytes were transferred.

Each endpoint advertises its own receive window. When the first forward packet is a client SYN, the forward initial-window feature normally describes the client's receive capacity, while the backward feature normally describes the server's. These values are not payload size, total transferred bytes, or the TCP congestion window. UDP has no TCP receive window, so an unavailable sentinel such as `-1` or `0` may appear depending on extractor version.

#### Feature meanings

| Column | Meaning |
|---|---|
| `Fwd Bytes/Bulk Avg` | Average forward payload bytes per detected forward bulk. |
| `Fwd Packet/Bulk Avg` | Average packets per detected forward bulk transfer. |
| `Fwd Bulk Rate Avg` | Total forward bulk payload bytes divided by total forward bulk duration, in bytes per second. |
| `Bwd Bytes/Bulk Avg` | Average backward payload bytes per detected backward bulk. |
| `Bwd Packet/Bulk Avg` | Average packets per detected backward bulk transfer. |
| `Bwd Bulk Rate Avg` | Total backward bulk payload bytes divided by total backward bulk duration, in bytes per second. |
| `Subflow Fwd Packets` | Average number of forward packets per detected subflow. |
| `Subflow Fwd Bytes` | Average number of forward bytes per detected subflow. |
| `Subflow Bwd Packets` | Average number of backward packets per detected subflow. |
| `Subflow Bwd Bytes` | Average number of backward bytes per detected subflow. |
| `FWD Init Win Bytes` | TCP window value reported for the initial forward packet. It is an advertised receive-window field, not transferred bytes. In this dataset, `-1` is an unavailable or not-applicable sentinel. |
| `Bwd Init Win Bytes` | TCP window value reported for the backward direction. It is an advertised receive-window field, not transferred bytes. In this dataset, `-1` is an unavailable or not-applicable sentinel. |
| `Fwd Act Data Pkts` | Number of forward packets carrying at least one byte of TCP payload. |
| `Fwd Seg Size Min` | Minimum forward packet header-byte count in the published implementation. Despite the name, it is not the minimum forward payload size. |

### Active and idle periods

CICFlowMeter divides sufficiently long flows into alternating **active** and **idle** periods according to its activity timeout. These statistics use microseconds in this export.

| Column | Meaning |
|---|---|
| `Active Mean` | Mean duration of active periods. |
| `Active Std` | Standard deviation of active-period durations. |
| `Active Max` | Maximum active-period duration. |
| `Active Min` | Minimum active-period duration. |
| `Idle Mean` | Mean duration of idle periods. |
| `Idle Std` | Standard deviation of idle-period durations. |
| `Idle Max` | Maximum idle-period duration. |
| `Idle Min` | Minimum idle-period duration. |

## Data-quality evidence

The feature meanings above are static documentation. The recorded evidence for missing values, infinities, invalid values, zero-duration flows, duplicates, class imbalance, cleaning decisions, and the final cleaned schema remains in [Notebook 1](notebooks/01_data_exploration.ipynb).
