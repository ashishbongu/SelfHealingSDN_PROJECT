import time
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (CONFIG_DISPATCHER, MAIN_DISPATCHER,
                                    set_ev_cls)
from ryu.ofproto import ofproto_v1_3
import networkx as nx

# (switch, next switch) -> output port on that switch (matches topology.py)
PORT = {
    (1, 2): 2, (2, 1): 1,
    (1, 3): 3, (3, 1): 1,
    (2, 4): 2, (4, 2): 1,
    (3, 4): 2, (4, 3): 2,
}
# Reverse lookup: (switch, port) -> neighbour switch
NEIGHBOR = {(sw, port): nxt for (sw, nxt), port in PORT.items()}

# Link costs (lower = preferred). Keys are sorted pairs.
LINK_COST = {(1, 2): 1, (2, 4): 1, (1, 3): 2, (3, 4): 2}

# Hosts: name -> (MAC, switch id, port on that switch)
HOSTS = {
    'h1': ('00:00:00:00:00:01', 1, 1),
    'h4': ('00:00:00:00:00:04', 4, 3),
}


def now():
    t = time.time()
    return time.strftime('%H:%M:%S', time.localtime(t)) + '.%03d' % int((t % 1) * 1000)


class SelfHealing(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dps = {}             # switch id -> datapath
        self.paths = {}           # (src, dst) -> current path, e.g. [1, 2, 4]
        self.down_ports = set()   # (switch, port) pairs currently down

        self.G = nx.Graph()
        for (a, b), w in LINK_COST.items():
            self.G.add_edge(a, b, weight=w)

    # ---------- switch connects ----------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_connected(self, ev):
        dp = ev.msg.datapath
        self.dps[dp.id] = dp
        self.logger.info("Switch s%d connected", dp.id)
        if len(self.dps) == 4:
            self.install_all_paths()

    # ---------- failure / recovery detection ----------
    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status(self, ev):
        t_detect = time.time()
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto

        nbr = NEIGHBOR.get((dp.id, msg.desc.port_no))
        if nbr is None:
            return  # host-facing port
        link = tuple(sorted((dp.id, nbr)))
        this_end = (dp.id, msg.desc.port_no)
        other_end = (nbr, PORT[(nbr, dp.id)])

        is_down = bool(msg.desc.state & ofp.OFPPS_LINK_DOWN) or \
                  bool(msg.desc.config & ofp.OFPPC_PORT_DOWN)

        if is_down:
            self.down_ports.add(this_end)
        else:
            self.down_ports.discard(this_end)

        # A link is usable only if BOTH ends are up
        link_is_down = this_end in self.down_ports or other_end in self.down_ports

        if link_is_down and self.G.has_edge(*link):
            self.link_down(link, t_detect)
        elif not link_is_down and not self.G.has_edge(*link):
            self.link_up(link)

    def link_down(self, link, t_detect):
        affected = [k for k, p in self.paths.items()
                    if any(set((p[i], p[i + 1])) == set(link)
                           for i in range(len(p) - 1))]
        self.logger.info("=" * 50)
        self.logger.info("ALERT: Network Failure Detected")
        self.logger.info("  Link: s%d-s%d   Status: DOWN", *link)
        self.logger.info("  Affected flows: %d   Detected: %s",
                         len(affected), now())

        self.G.remove_edge(*link)
        self.install_all_paths()

        ms = (time.time() - t_detect) * 1000
        self.logger.info("  Reroute rules sent %.1f ms after detection", ms)
        self.logger.info("=" * 50)

    def link_up(self, link):
        self.logger.info("Link s%d-s%d is UP again (%s)", *link, now())
        self.G.add_edge(*link, weight=LINK_COST[link])
        self.install_all_paths()

    # ---------- routing ----------
    def install_all_paths(self):
        self.install_path('h1', 'h4')
        self.install_path('h4', 'h1')

    def install_path(self, src, dst):
        dst_mac, dst_sw, dst_port = HOSTS[dst]
        src_sw = HOSTS[src][1]

        try:
            path = nx.shortest_path(self.G, src_sw, dst_sw, weight='weight')
        except nx.NetworkXNoPath:
            self.logger.info("No path %s -> %s !", src, dst)
            self.paths.pop((src, dst), None)
            return

        self.paths[(src, dst)] = path
        self.logger.info("Path %s -> %s : %s", src, dst,
                         " -> ".join("s%d" % s for s in path))

        for i, sw in enumerate(path):
            out_port = dst_port if i == len(path) - 1 else PORT[(sw, path[i + 1])]
            self.add_flow(self.dps[sw], dst_mac, out_port)

    def add_flow(self, dp, dst_mac, out_port):
        parser = dp.ofproto_parser
        ofp = dp.ofproto
        match = parser.OFPMatch(eth_dst=dst_mac)
        actions = [parser.OFPActionOutput(out_port)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=dp, priority=10,
                                match=match, instructions=inst)
        dp.send_msg(mod)
