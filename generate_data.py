import csv
import re
import time
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel

OUT = 'data/labels.csv'
DST = '10.0.0.4'
BASE_DELAY = 5     # ms, same as topology.py
ROUNDS = 1         # repeat the whole list this many times (more data)

# name, label, seconds, load, added delay start/end (ms), loss start/end (%)
# label 0 = healthy, 1 = at risk (link degrading)
SCENARIOS = [
    ('idle',       0, 30, None,  0,   0,   0,  0),
    ('load_2M',    0, 25, '2M',  0,   0,   0,  0),
    ('load_4M',    0, 25, '4M',  0,   0,   0,  0),
    ('delay_ramp', 1, 40, '2M',  20,  100, 0,  0),
    ('loss_ramp',  1, 40, '2M',  0,   0,   2,  15),
    ('congestion', 1, 30, 'max', 30,  30,  0,  0),
]


def set_link(link, added_delay, loss):
    for intf in (link.intf1, link.intf2):
        intf.config(bw=10, delay='%dms' % (BASE_DELAY + added_delay),
                    loss=loss)


def sample(h1):
    out = h1.cmd('ping -c 5 -i 0.2 -W 1 %s' % DST)
    m = re.search(r'([\d.]+)% packet loss', out)
    loss = float(m.group(1)) if m else 100.0
    m = re.search(r'= [\d.]+/([\d.]+)/[\d.]+/([\d.]+) ms', out)
    if m:
        rtt, jitter = float(m.group(1)), float(m.group(2))
    else:
        rtt, jitter = 1000.0, 0.0      # every ping lost
    return rtt, jitter, loss


def main():
    net = Mininet(controller=None, switch=OVSSwitch, link=TCLink,
                  autoSetMacs=False)
    net.addController('c0', controller=RemoteController,
                      ip='127.0.0.1', port=6653)
    h1 = net.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
    h4 = net.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')
    s1, s2, s3, s4 = [net.addSwitch('s%d' % i, protocols='OpenFlow13',
                                    failMode='secure') for i in range(1, 5)]
    # same link order as topology.py (port numbers depend on it)
    net.addLink(h1, s1)
    net.addLink(s1, s2, bw=10, delay='5ms')
    net.addLink(s1, s3, bw=10, delay='5ms')
    net.addLink(s2, s4, bw=10, delay='5ms')
    net.addLink(s3, s4, bw=10, delay='5ms')
    net.addLink(h4, s4)

    net.start()
    net.staticArp()
    print('Waiting for switches to connect to Ryu...')
    time.sleep(6)
    h1.cmd('ping -c 3 %s' % DST)       # warm-up
    s24 = net.linksBetween(s2, s4)[0]
    h4.cmd('iperf3 -s -D > /dev/null 2>&1')

    f = open(OUT, 'w', newline='')
    w = csv.writer(f)
    w.writerow(['timestamp', 'scenario', 'label', 'rtt_ms', 'jitter_ms',
                'loss_pct'])

    total = sum(s[2] for s in SCENARIOS) * ROUNDS
    print('Collecting data: about %d seconds' % (total + 6 * len(SCENARIOS) * ROUNDS))

    for r in range(ROUNDS):
        for name, label, secs, load, d0, d1, l0, l1 in SCENARIOS:
            print('[round %d] %s (label %d, %d s)' % (r + 1, name, label, secs))
            set_link(s24, d0, l0)
            if load == 'max':
                h1.cmd('iperf3 -c %s -t 600 > /dev/null 2>&1 &' % DST)
            elif load:
                h1.cmd('iperf3 -c %s -t 600 -b %s > /dev/null 2>&1 &'
                       % (DST, load))
            time.sleep(3)              # let traffic settle

            start = time.time()
            while time.time() - start < secs:
                frac = (time.time() - start) / secs
                set_link(s24, round(d0 + (d1 - d0) * frac),
                         round(l0 + (l1 - l0) * frac))
                rtt, jit, loss = sample(h1)
                w.writerow([round(time.time(), 3), name, label,
                            rtt, jit, loss])
                f.flush()

            h1.cmd('pkill -f "iperf3 -c"')
            set_link(s24, 0, 0)        # back to healthy
            time.sleep(3)

    f.close()
    h4.cmd('pkill iperf3')
    net.stop()
    print('Done. Saved %s' % OUT)


if __name__ == '__main__':
    setLogLevel('warning')
    main()
