from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, set_ev_cls
from ryu.topology import event

from .common import TopologyController


class BaselineController(TopologyController):
    """Shortest-path forwarding with no automatic repair."""

    @set_ev_cls(event.EventLinkDelete)
    def link_delete(self, ev):
        self.logger.warning(
            "LINK DOWN s%s-s%s (baseline: no recovery)",
            ev.link.src.dpid,
            ev.link.dst.dpid,
        )
        self.rebuild_topology()

