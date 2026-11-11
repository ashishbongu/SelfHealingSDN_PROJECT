import os
import time
from collections import deque

CSV_PATH = 'data/telemetry.csv'
LOG_PATH = 'data/alerts.log'

CONG_AVG_PCT = 55.0   # congestion if 3-second average utilization >= this
WINDOW = 3
ABN_FACTOR = 5.0      # abnormal if rate > factor x normal
ABN_MIN_MBPS = 2.0    # ...and above this absolute rate
WARMUP = 15           # samples used to learn "normal" before judging
COOLDOWN = 10         # seconds between repeats of the same alert

HOSTS = {(1, 1): 'H1', (4, 3): 'H4'}   # (switch, port) -> host name

recent = {}       # link -> last utilization values
baseline = {}     # host port -> normal Mbps (running average)
seen = {}         # host port -> number of samples
last_alert = {}   # alert key -> time of last alert


def emit(key, lines):
    t = time.time()
    if t - last_alert.get(key, 0) < COOLDOWN:
        return
    last_alert[key] = t
    lines = ['=' * 40] + lines + ['  Time: ' + time.strftime('%H:%M:%S')]
    text = '\n'.join(lines)
    print(text, flush=True)
    with open(LOG_PATH, 'a') as f:
        f.write(text + '\n')


def follow(path):
    while not os.path.exists(path):
        time.sleep(1)
    f = open(path)
    f.seek(0, 2)              # start at the end: only new data
    while True:
        line = f.readline()
        if not line:
            time.sleep(0.2)
            continue
        yield line


def check_link(link, util, tx):
    d = recent.setdefault(link, deque(maxlen=WINDOW))
    d.append(util)
    if len(d) == WINDOW and sum(d) / WINDOW >= CONG_AVG_PCT:
        emit(('cong', link), [
            'ALERT: Network Congestion',
            '  Link: %s' % link,
            '  Utilization (3 s avg): %.0f%%' % (sum(d) / WINDOW),
            '  Current load: %.1f Mbps' % tx])


def check_host(key, rx):
    name = HOSTS[key]
    n = seen.get(key, 0)
    b = baseline.get(key, rx)
    ref = max(b, 0.1)
    if n >= WARMUP and rx > ABN_MIN_MBPS and rx > ABN_FACTOR * ref:
        emit(('abn', key), [
            'ALERT: Abnormal Traffic Detected',
            '  Source: Host %s' % name,
            '  Normal traffic: ~%.1f Mbps' % b,
            '  Current traffic: %.1f Mbps' % rx,
            '  Deviation: %.1fx' % (rx / ref)])
        return                # do not learn from abnormal traffic
    baseline[key] = rx if key not in baseline else 0.9 * b + 0.1 * rx
    seen[key] = n + 1


print('Watching %s ... (Ctrl+C to stop)' % CSV_PATH, flush=True)
for line in follow(CSV_PATH):
    p = line.strip().split(',')
    try:
        sw, port, link = int(p[1]), int(p[2]), p[3]
        tx, rx, util = float(p[4]), float(p[5]), float(p[8])
    except (ValueError, IndexError):
        continue                  # header or half-written line
    if link == 'host':
        if (sw, port) in HOSTS:
            check_host((sw, port), rx)   # rx = traffic the host sends in
    elif sw == int(link[1]):             # one report per link, not two
        check_link(link, util, tx)
