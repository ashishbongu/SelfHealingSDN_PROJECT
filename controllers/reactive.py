import time

import networkx as nx
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, set_ev_cls
from ryu.topology import event

from .common import TopologyController


class ReactiveController(TopologyController):
    """Deletes affected destination flows and installs a new shortest path."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.installed_paths = {}

    def install_path(self, path, destination_mac, destination_port, idle_timeout=30):
        result = super().install_path(path, destination_mac, destination_port, idle_timeout)
        paths = self.installed_paths.setdefault(destination_mac, [])
        if path not in paths:
            paths.append(path)
        return result

    @staticmethod
    def uses_link(path, first, second):
        return any({path[i], path[i + 1]} == {first, second}
                   for i in range(len(path) - 1))

    @set_ev_cls(event.EventLinkDelete)
    def link_delete(self, ev):
        started = time.perf_counter()
        first, second = ev.link.src.dpid, ev.link.dst.dpid
        self.rebuild_topology()
        for destination_mac, paths in list(self.installed_paths.items()):
            for old_path in [path for path in paths
                             if self.uses_link(path, first, second)]:
                self.delete_path_flows(old_path, destination_mac)
                paths.remove(old_path)
                if destination_mac not in self.hosts:
                    continue
                destination_switch, destination_port = self.hosts[destination_mac]
                try:
                    new_path = nx.shortest_path(
                        self.graph, old_path[0], destination_switch
                    )
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    self.logger.error("No recovery path for %s", destination_mac)
                    continue
                self.install_path(new_path, destination_mac, destination_port)
                self.logger.warning(
                    "HEALED dst=%s old=%s new=%s processing_ms=%.1f",
                    destination_mac,
                    old_path,
                    new_path,
                    (time.perf_counter() - started) * 1000,
                )

    def delete_path_flows(self, path, destination_mac):
        for dpid in path:
            dp = self.datapaths.get(dpid)
            if dp is None:
                continue
            dp.send_msg(dp.ofproto_parser.OFPFlowMod(
                datapath=dp,
                command=dp.ofproto.OFPFC_DELETE,
                out_port=dp.ofproto.OFPP_ANY,
                out_group=dp.ofproto.OFPG_ANY,
                match=dp.ofproto_parser.OFPMatch(eth_dst=destination_mac),
            ))

