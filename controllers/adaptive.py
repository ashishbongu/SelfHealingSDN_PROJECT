from .baseline import BaselineController


class AdaptiveController(BaselineController):
    """Discovery/initial forwarding; policy decisions remain backend-owned."""

    def link_delete(self, ev):
        self.logger.warning(
            "LINK DOWN s%s-s%s; adaptive recovery decision pending",
            ev.link.src.dpid,
            ev.link.dst.dpid,
        )
        self.rebuild_topology()

