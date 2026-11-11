# SelfHealingSDN_PROJECT

A Software-Defined Network built with **Mininet**, **Open vSwitch** and the **Ryu** controller that:

1. routes traffic along the lowest-cost path (NetworkX),
2. **detects link failures** from OpenFlow port-status messages and **reroutes** traffic to a backup path,
3. **collects telemetry** (throughput, packets/s, utilisation, drops, errors) every second,
4. raises **rule-based alerts** (congestion, abnormal traffic),
5. can **generate labelled data** (healthy vs. degrading link) as the basis for an AI failure-prediction model.

> **Project status:** routing, telemetry and alerts are working and have been demonstrated (see [Results so far](#results-so-far)).
> The failure-recovery test, the AI model and the dashboard are the next steps (see [Roadmap](#roadmap)).

---

## Status at a glance

| Component | File | Status |
|---|---|---|
| VM + Ryu installation | – | Done (Ryu 4.34 working after the eventlet fix below) |
| Topology (4 switches, 2 hosts, 10 Mbit / 5 ms links) | `topology.py` | Done – `h1 ping h4`: 0 % loss |
| Shortest-path routing + failure/recovery logic | `controller.py` | Routing demonstrated; **failover test not yet captured** |
| Telemetry collector (port statistics -> CSV) | `telemetry.py` | Done – writing `data/telemetry.csv` |
| Alert system (congestion, abnormal traffic) | `alerts.py` | Done – alerts demonstrated |
| Training-data generator | `generate_data.py` | Written; run and inspect `data/labels.csv` |
| AI model (train + connect to controller) | – | Not started |
| Real-time dashboard | – | Not started |

---

## Topology

```
 H1 ---- S1 ======== S2 ======== S4 ---- H4        normal path : H1 -> S1 -> S2 -> S4 -> H4   (cost 1+1)
          \                     /
           \====== S3 =========/                    backup path : H1 -> S1 -> S3 -> S4 -> H4   (cost 2+2)

 all switch-to-switch links: 10 Mbit/s, 5 ms delay (TCLink)
 H1 = 10.0.0.1 (00:00:00:00:00:01)     H4 = 10.0.0.4 (00:00:00:00:00:04)
```

**Port map** (decided by the order of `addLink` calls in `topology.py` – never reorder them):

| Switch | Port 1 | Port 2 | Port 3 |
|---|---|---|---|
| s1 | h1 | s2 | s3 |
| s2 | s1 | s4 | – |
| s3 | s1 | s4 | – |
| s4 | s2 | s3 | h4 |

`controller.py` and `telemetry.py` hard-code this map (`PORT` dictionary). `generate_data.py` builds the same topology in the same order. If you change the topology, update all three.

---

## Repository layout

```
sdn-project/
├── topology.py        Mininet topology + CLI (static ARP, fixed MACs)
├── controller.py      Ryu app "SelfHealing": routing, failure detection, rerouting
├── telemetry.py       Ryu app "Telemetry": polls port stats every 1 s -> data/telemetry.csv
├── alerts.py          Tails telemetry.csv, prints/logs alerts -> data/alerts.log
├── generate_data.py   Mininet run that records labelled samples -> data/labels.csv
├── data/              Created by you: telemetry.csv, alerts.log, labels.csv
└── venv/              Python virtual environment (Ryu, NetworkX)
```

---

## Environment used

| Item | Value |
|---|---|
| Host | Windows PC, Oracle VirtualBox |
| VM | `sdn-lab`, Ubuntu 22.10 64-bit, 4 GB RAM, 3 CPUs, 30 GB disk, NAT networking |
| Python | 3.10 (virtual environment in `~/sdn-project/venv`) |
| SDN stack | Mininet, Open vSwitch (`ovsk`), Ryu 4.34, OpenFlow 1.3 |
| Libraries | `networkx` (path calculation) |

### Setup

```bash
# system packages
sudo apt update
sudo apt install -y mininet openvswitch-switch iperf3 python3-venv

# project + virtual environment
mkdir -p ~/sdn-project/data && cd ~/sdn-project
python3 -m venv venv
source venv/bin/activate
pip install ryu==4.34 networkx
```

**Ryu 4.34 on Python 3.10 needs a workaround.** Out of the box `ryu-manager` fails with
`ImportError: cannot import name 'ALREADY_HANDLED' from 'eventlet.wsgi'`. The fix that worked on this VM:

```bash
pip install "eventlet==0.33.3" "dnspython==2.2.1"
sed -i 's/from eventlet.wsgi import ALREADY_HANDLED/ALREADY_HANDLED = []/' \
    venv/lib/python3.10/site-packages/ryu/app/wsgi.py
ryu-manager --version        # -> ryu-manager 4.34
```

(The patch only touches Ryu's REST/WSGI module, which this project does not use.)

### Sanity checks that were done

```bash
# 1. Ryu + Open vSwitch work together (stock learning-switch app)
ryu-manager ryu.app.simple_switch_13
sudo mn --topo single,3 --controller remote --switch ovsk,protocols=OpenFlow13
mininet> pingall
```

---

## How to run

Run everything from the project root (`~/sdn-project`) because the scripts use the relative path `data/`.
**Start order matters: controller first, then Mininet.**

**Terminal 1 – controller + telemetry (venv)**
```bash
cd ~/sdn-project && source venv/bin/activate
mkdir -p data
ryu-manager controller.py telemetry.py
# expected:  Switch s1..s4 connected
#            Path h1 -> h4 : s1 -> s2 -> s4
#            Path h4 -> h1 : s4 -> s2 -> s1
```

**Terminal 2 – network (system Python, needs root)**
```bash
cd ~/sdn-project
sudo mn -c                    # clean up leftovers from earlier runs
sudo python3 topology.py
mininet> h1 ping -c 3 h4
```

**Terminal 3 – alerts**
```bash
cd ~/sdn-project
python3 alerts.py             # prints new alerts and appends them to data/alerts.log
```

**Generate traffic (Mininet CLI)**
```bash
mininet> h4 iperf3 -s > /dev/null &
mininet> h1 iperf3 -c 10.0.0.4 -t 15
mininet> sh tail -n 12 data/telemetry.csv
```

**Failure test (Mininet CLI)** – while a ping or iperf3 is running:
```bash
mininet> link s2 s4 down      # controller should log "Network Failure Detected" and switch to s1 -> s3 -> s4
mininet> link s2 s4 up        # controller logs "Link s2-s4 is UP again" and returns to s1 -> s2 -> s4
```

**Collect AI training data** (stop `topology.py` first – both build the same network; keep the controller running)
```bash
sudo mn -c
sudo python3 generate_data.py     # ~4 minutes, writes data/labels.csv
```

Cleanup after a crash: `sudo mn -c`.

---

## How it works

### `controller.py` – self-healing routing

* **Graph:** NetworkX graph of the four switches; edge weights from `LINK_COST` (`s1-s2`, `s2-s4` = 1; `s1-s3`, `s3-s4` = 2), so the S2 path is preferred.
* **Rules:** once all four switches are connected, it computes the shortest path for `h1 -> h4` and `h4 -> h1` and installs one flow per switch on the path (match `eth_dst`, priority 10, output port from the `PORT` map). Static ARP in `topology.py` means no ARP flooding is needed.
* **Failure detection:** handles `EventOFPPortStatus`. A link counts as down if *either* end reports `LINK_DOWN` or `PORT_DOWN`; the first message triggers recovery and the second (from the other end) is ignored because the edge is already removed.
* **Recovery:** logs the alert (link, affected flows, detection time), removes the edge from the graph, recomputes paths, reinstalls flows, and logs how many milliseconds passed between detection and the rules being sent.
* **Restoration:** when both ends are up again, the edge returns to the graph and traffic moves back to the cheaper path.

### `telemetry.py` – data collection

Sends an `OFPPortStatsRequest` to every switch each second and appends one row per port to `data/telemetry.csv`:

| Column | Meaning |
|---|---|
| `timestamp` | Unix time of the reply |
| `switch`, `port` | Datapath id and port number |
| `link` | `s1-s2`-style name for inter-switch ports, `host` for host-facing ports |
| `tx_mbps`, `rx_mbps` | Transmit / receive rate over the last interval |
| `tx_pps`, `rx_pps` | Packets per second |
| `utilization_pct` | `max(tx, rx) / 10 Mbit * 100` (`LINK_CAPACITY_MBPS = 10`) |
| `drops`, `errors` | Dropped packets / errors in the interval |

### `alerts.py` – rule-based alerts

Follows the CSV (starting at the end, so only new data is judged) and prints plus logs alerts to `data/alerts.log`.

| Alert | Rule | Parameters |
|---|---|---|
| Network Congestion | 3-second average utilisation of a link ≥ threshold | `CONG_AVG_PCT = 55`, `WINDOW = 3` |
| Abnormal Traffic | Host sends > 5 x its learned normal rate **and** > 2 Mbps | `ABN_FACTOR = 5`, `ABN_MIN_MBPS = 2`, 15-sample warm-up, baseline is a running average that does not learn from abnormal samples |
| (both) | Same alert is not repeated within `COOLDOWN = 10` s | |

Network failure alerts are printed by the controller itself (they come from OpenFlow events, not from the CSV).

### `generate_data.py` – labelled training data

Builds the same topology, then walks through scenarios on the **s2–s4** link while sampling `ping` (5 packets, 0.2 s apart) from h1 to h4. Each sample is one row in `data/labels.csv`:
`timestamp, scenario, label, rtt_ms, jitter_ms, loss_pct`.

| Scenario | Label | Duration | Load | Link change on s2–s4 |
|---|---|---|---|---|
| `idle` | 0 healthy | 30 s | none | none |
| `load_2M` | 0 healthy | 25 s | 2 Mbit/s | none |
| `load_4M` | 0 healthy | 25 s | 4 Mbit/s | none |
| `delay_ramp` | 1 at risk | 40 s | 2 Mbit/s | +20 -> +100 ms delay |
| `loss_ramp` | 1 at risk | 40 s | 2 Mbit/s | 2 -> 15 % loss |
| `congestion` | 1 at risk | 30 s | max (iperf3 unlimited) | +30 ms delay |

Increase `ROUNDS` at the top of the file to repeat the list and collect more samples.

---

## Results so far

All results below come from runs on the `sdn-lab` VM.

| Test | Result |
|---|---|
| Ryu + OVS sanity (`simple_switch_13`, `mn --topo single,3`) | Controller received packet-ins; `pingall` run |
| Custom topology: `h1 ping -c 3 h4` | **0 % loss**, RTT min/avg/max = 26.0 / 35.5 / 42.4 ms (two 5 ms links each way give ≥ 20 ms; the rest is Mininet/VM overhead) |
| Controller start | s1–s4 connected; **h1 -> h4: s1 -> s2 -> s4** and **h4 -> h1: s4 -> s2 -> s1** installed |
| `iperf3` 10 s (h1 -> h4) | Sender 6.88 Mbit/s (1 retransmit) |
| `iperf3` 15 s (h1 -> h4) | Sender 9.75 Mbit/s, 0 retransmits – throughput is capped by the 10 Mbit/s links, as intended |
| Telemetry | `data/telemetry.csv` filling with one row per port per second (all-zero rows when idle, as expected) |
| Alerts during `iperf3` | **Abnormal Traffic**: Host H1, normal ~0.0 Mbps -> 8.1 Mbps (81.5x) and 6.6 Mbps (65.8x). **Network Congestion**: `s1-s2` and `s2-s4` at 60 % and 57 % (3 s average) |

Notes on reading these numbers:

* The "receiver" line of `iperf3` covers a longer interval than the sender's (for example 16.6 s vs 15 s) because data is still draining through the 10 Mbit / 5 ms links after the sender finishes. It is queueing, not loss.
* In the congestion alerts, "Current load" is the latest one-second sample, while the percentage is the 3-second average, so they do not always match (for instance 9.7 Mbps shown with 57 %).
* The abnormal-traffic alert fires for any `iperf3` run after an idle period, because the learned baseline for H1 is ~0 Mbps. That is the intended behaviour of the rule; to avoid it, run light background traffic during the warm-up.

---

## Known limitations

* **Failover not yet demonstrated.** The recovery logic has been reviewed against the port map (a `link s2 s4 down` should move both directions to `s1 -> s3 -> s4` and back after `link s2 s4 up`), but a captured run with the "Network Failure Detected" log and a ping/iperf3 recovery check is still missing.
* **Only two hosts, one flow pair.** The controller installs rules for `h1 <-> h4` only and matches on destination MAC. Adding hosts means extending `HOSTS`, `PORT` and the install logic.
* **Old rules are not deleted** from switches that leave the path after a reroute. They are harmless here (traffic no longer reaches them) but should be cleaned up for larger topologies.
* **Hard-coded wiring.** `PORT` in `controller.py` and `telemetry.py` must match `topology.py`.
* **Relative paths.** `data/telemetry.csv` and `data/alerts.log` require running from the project root with `data/` existing.
* **Rule-based alerts only.** Thresholds are fixed; no model is involved yet.
* **Ubuntu 22.10 is an end-of-life release.** It works for this project, but apt may need the `old-releases` mirror for new packages, and an LTS release (22.04) is a safer base.

---

## Roadmap

1. **Failover test and MTTR.** Run `link s2 s4 down` during `ping -i 0.05` or `iperf3`, record the controller's "rules sent N ms after detection" line and the length of the ping gap; repeat 10 times and average.
2. **Check the training data.** Open `data/labels.csv`, confirm the rows for each scenario look different (rising RTT/jitter/loss in `delay_ramp`/`loss_ramp`).
3. **Train a model.** Start with a Random Forest (classification) or Isolation Forest (anomaly detection) on `rtt_ms`, `jitter_ms`, `loss_pct`, plus utilisation features from `telemetry.csv`; hold out whole scenarios for testing and report accuracy, precision/recall and false-positive rate.
4. **Connect AI to the controller.** Feed live measurements to the model; when predicted risk for s2–s4 is high, raise that link's cost in `LINK_COST`/the graph and reroute *before* it fails.
5. **Dashboard.** Show topology, utilisation, latency, loss, link status and alerts in real time (for example Flask + Server-Sent Events reading the CSV files or a small database).
6. **DDoS / abnormal-traffic ML** as a later extension of `alerts.py`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ImportError: cannot import name 'ALREADY_HANDLED'` | Apply the eventlet / dnspython fix in [Setup](#setup) |
| `FileNotFoundError: data/telemetry.csv` | `mkdir -p data` and start `ryu-manager` from the project root |
| Switches do not connect / Mininet cannot reach the controller | Start the controller first; check it listens on port 6653 (`ss -ltnp | grep 6653`) |
| Leftover interfaces or "File exists" errors | `sudo mn -c` |
| `ping` fails right after start | Wait until the controller prints the two `Path ...` lines, then retry |
| `alerts.py` prints nothing | It only judges **new** lines; start it before generating traffic and make sure `telemetry.py` is loaded in `ryu-manager` |
| `generate_data.py` collects nothing useful | The controller must be running and `topology.py` must be stopped (same switch names/ports) |

---

## Housekeeping

* An empty file named `pingall` is in the project folder (probably created by typing `pingall > …` or similar in a shell). It can be deleted: `rm pingall`.
* Suggested `.gitignore`:
  ```
  venv/
  data/
  __pycache__/
  ```
