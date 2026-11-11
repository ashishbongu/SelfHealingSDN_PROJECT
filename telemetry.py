import csv
import os
import time
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
from ryu.lib import hub
from ryu.ofproto import ofproto_v1_3

# (switch, next switch) -> port on that switch (same wiring as controller.py)
PORT = {
    (1, 2): 2, (2, 1): 1,
    (1, 3): 3, (3, 1): 1,
    (2, 4): 2, (4, 2): 1,
    (3, 4): 2, (4, 3): 2,
}
# (switch, port) -> neighbour switch
NEIGHBOR = {(sw, p): nxt for (sw, nxt), p in PORT.items()}

LINK_CAPACITY_MBPS = 10.0
INTERVAL = 1.0
CSV_PATH = 'data/telemetry.csv'
HEADER = ['timestamp', 'switch', 'port', 'link',
          'tx_mbps', 'rx_mbps', 'tx_pps', 'rx_pps',
          'utilization_pct', 'drops', 'errors']


class Telemetry(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dps = {}
        self.prev = {}   # (switch, port) -> (time, counters)

        new_file = not os.path.exists(CSV_PATH)
        self.f = open(CSV_PATH, 'a', newline='')
        self.w = csv.writer(self.f)
        if new_file:
            self.w.writerow(HEADER)
            self.f.flush()

        hub.spawn(self.poll_loop)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change(self, ev):
        dp = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.dps[dp.id] = dp
        elif dp.id in self.dps:
            del self.dps[dp.id]

    def poll_loop(self):
        while True:
            for dp in list(self.dps.values()):
                parser = dp.ofproto_parser
                req = parser.OFPPortStatsRequest(dp, 0, dp.ofproto.OFPP_ANY)
                dp.send_msg(req)
            hub.sleep(INTERVAL)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def stats_reply(self, ev):
        dpid = ev.msg.datapath.id
        t = time.time()
        for st in ev.msg.body:
            if st.port_no > 0xffffff00:      # skip the special LOCAL port
                continue
            key = (dpid, st.port_no)
            cur = (st.tx_bytes, st.rx_bytes, st.tx_packets, st.rx_packets,
                   st.tx_dropped + st.rx_dropped,
                   st.tx_errors + st.rx_errors)

            if key in self.prev:
                t0, c0 = self.prev[key]
                dt = t - t0
                if dt > 0:
                    tx_mbps = (cur[0] - c0[0]) * 8 / dt / 1e6
                    rx_mbps = (cur[1] - c0[1]) * 8 / dt / 1e6
                    tx_pps = (cur[2] - c0[2]) / dt
                    rx_pps = (cur[3] - c0[3]) / dt
                    drops = cur[4] - c0[4]
                    errors = cur[5] - c0[5]
                    util = max(tx_mbps, rx_mbps) / LINK_CAPACITY_MBPS * 100

                    nbr = NEIGHBOR.get(key)
                    link = ('s%d-s%d' % tuple(sorted((dpid, nbr)))
                            if nbr else 'host')
                    self.w.writerow([round(t, 3), dpid, st.port_no, link,
                                     round(tx_mbps, 3), round(rx_mbps, 3),
                                     round(tx_pps, 1), round(rx_pps, 1),
                                     round(util, 1), drops, errors])
                    self.f.flush()
            self.prev[key] = (t, cur)
