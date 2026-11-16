import networkx as nx
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, set_ev_cls
from ryu.topology import event

from .common import TopologyController


class FastFailoverController(TopologyController):
    """Installs OpenFlow fast-failover groups with watch-port buckets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_ids = {}

    def install_routes(self):
        for destination_mac, (destination_switch, destination_port) in self.hosts.items():
            group_id = self.group_ids.setdefault(destination_mac, len(self.group_ids) + 1)
            distances = nx.single_source_shortest_path_length(
                self.graph, destination_switch
            )
            for dpid, dp in self.datapaths.items():
                if dpid == destination_switch:
                    actions = [dp.ofproto_parser.OFPActionOutput(destination_port)]
                else:
                    candidates = sorted(
                        (neighbor for neighbor in self.graph.neighbors(dpid)
                         if distances.get(neighbor, 10**9) < distances.get(dpid, 10**9))
                    )
                    ports = [self.link_ports[(dpid, neighbor)] for neighbor in candidates]
                    if not ports:
                        continue
                    self.install_group(dp, group_id, ports)
                    actions = [dp.ofproto_parser.OFPActionGroup(group_id)]
                self.add_flow(
                    dp, 10,
                    dp.ofproto_parser.OFPMatch(eth_dst=destination_mac),
                    actions,
                )

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_event(self, ev):
        # The base handler learns the host location; this second step replaces
        # the temporary direct flow with the fast-failover group flow.
        super().packet_in_event(ev)
        self.install_routes()

    def install_group(self, dp, group_id, ports):
        parser, ofp = dp.ofproto_parser, dp.ofproto
        buckets = [
            parser.OFPBucket(
                watch_port=port,
                watch_group=ofp.OFPG_ANY,
                actions=[parser.OFPActionOutput(port)],
            )
            for port in ports
        ]
        dp.send_msg(parser.OFPGroupMod(
            dp, ofp.OFPGC_MODIFY, ofp.OFPGT_FF, group_id, buckets
        ))

    @set_ev_cls([event.EventSwitchEnter, event.EventLinkAdd])
    def topology_change(self, _ev):
        self.rebuild_topology()
        self.install_routes()

    @set_ev_cls(event.EventLinkDelete)
    def link_delete(self, ev):
        self.logger.warning(
            "LINK DOWN s%s-s%s; switch-local FF handles primary failure",
            ev.link.src.dpid,
            ev.link.dst.dpid,
        )
        self.rebuild_topology()
        self.install_routes()
