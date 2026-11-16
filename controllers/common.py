import networkx as nx
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib.packet import ethernet, ether_types, packet
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event
from ryu.topology.api import get_link, get_switch


BROADCAST = "ff:ff:ff:ff:ff:ff"
PORT_MAX = 0xFFFFFF00


class TopologyController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.graph = nx.Graph()
        self.datapaths = {}
        self.switch_ports = {}
        self.link_ports = {}
        self.isl_ports = set()
        self.hosts = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features(self, ev):
        dp = ev.msg.datapath
        self.datapaths[dp.id] = dp
        self.add_flow(
            dp,
            0,
            dp.ofproto_parser.OFPMatch(),
            [dp.ofproto_parser.OFPActionOutput(
                dp.ofproto.OFPP_CONTROLLER, dp.ofproto.OFPCML_NO_BUFFER
            )],
        )
        self.rebuild_topology()

    def add_flow(self, dp, priority, match, actions, idle_timeout=0):
        parser, ofp = dp.ofproto_parser, dp.ofproto
        instructions = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(parser.OFPFlowMod(
            datapath=dp,
            priority=priority,
            match=match,
            instructions=instructions,
            idle_timeout=idle_timeout,
        ))

    def rebuild_topology(self):
        self.graph.clear()
        self.link_ports.clear()
        self.isl_ports.clear()
        for switch in get_switch(self, None):
            self.graph.add_node(switch.dp.id)
            self.switch_ports[switch.dp.id] = [
                port.port_no for port in switch.ports if port.port_no < PORT_MAX
            ]
        for link in get_link(self, None):
            self.graph.add_edge(link.src.dpid, link.dst.dpid)
            self.link_ports[(link.src.dpid, link.dst.dpid)] = link.src.port_no
            self.isl_ports.add((link.src.dpid, link.src.port_no))
            self.isl_ports.add((link.dst.dpid, link.dst.port_no))
        self.logger.info("Topology switches=%s links=%s",
                         sorted(self.graph.nodes), sorted(self.graph.edges))

    @set_ev_cls([event.EventSwitchEnter, event.EventSwitchLeave, event.EventLinkAdd])
    def topology_change(self, _ev):
        self.rebuild_topology()

    def install_path(self, path, destination_mac, destination_port, idle_timeout=30):
        first_output = None
        for index, dpid in enumerate(path):
            output = (
                destination_port
                if index == len(path) - 1
                else self.link_ports[(dpid, path[index + 1])]
            )
            if first_output is None:
                first_output = output
            dp = self.datapaths[dpid]
            self.add_flow(
                dp,
                10,
                dp.ofproto_parser.OFPMatch(eth_dst=destination_mac),
                [dp.ofproto_parser.OFPActionOutput(output)],
                idle_timeout,
            )
        return first_output

    def packet_in(self, ev):
        msg = ev.msg
        dp = msg.datapath
        in_port = msg.match["in_port"]
        frame = packet.Packet(msg.data).get_protocol(ethernet.ethernet)
        if frame is None or frame.ethertype in (ether_types.ETH_TYPE_LLDP,
                                                ether_types.ETH_TYPE_IPV6):
            return
        if (dp.id, in_port) not in self.isl_ports:
            self.hosts[frame.src] = (dp.id, in_port)
        if frame.dst == BROADCAST or frame.dst not in self.hosts:
            self.flood_edge_ports(msg, dp.id, in_port)
            return
        destination_switch, destination_port = self.hosts[frame.dst]
        try:
            path = nx.shortest_path(self.graph, dp.id, destination_switch)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            self.logger.warning("No path from s%s to s%s", dp.id, destination_switch)
            return
        output = self.install_path(path, frame.dst, destination_port)
        dp.send_msg(dp.ofproto_parser.OFPPacketOut(
            datapath=dp, buffer_id=dp.ofproto.OFP_NO_BUFFER,
            in_port=in_port, actions=[dp.ofproto_parser.OFPActionOutput(output)],
            data=msg.data,
        ))

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_event(self, ev):
        self.packet_in(ev)

    def flood_edge_ports(self, msg, source_switch, source_port):
        for dpid, dp in self.datapaths.items():
            actions = [
                dp.ofproto_parser.OFPActionOutput(port)
                for port in self.switch_ports.get(dpid, [])
                if (dpid, port) not in self.isl_ports
                and (dpid, port) != (source_switch, source_port)
            ]
            if actions:
                dp.send_msg(dp.ofproto_parser.OFPPacketOut(
                    datapath=dp,
                    buffer_id=dp.ofproto.OFP_NO_BUFFER,
                    in_port=dp.ofproto.OFPP_CONTROLLER,
                    actions=actions,
                    data=msg.data,
                ))

