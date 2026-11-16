from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController


def build():
    net = Mininet(controller=None, switch=OVSSwitch, link=TCLink, autoSetMacs=True)
    net.addController("c0", controller=RemoteController,
                      ip="127.0.0.1", port=6653)
    hosts = [net.addHost("h1"), net.addHost("h4")]
    switches = {f"s{i}": net.addSwitch(f"s{i}", protocols="OpenFlow13",
                                        failMode="secure")
                for i in range(1, 10)}
    net.addLink(hosts[0], switches["s1"])
    net.addLink(hosts[1], switches["s9"])
    links = [
        ("s1", "s2"), ("s1", "s3"), ("s2", "s4"), ("s2", "s5"),
        ("s3", "s5"), ("s3", "s6"), ("s4", "s7"), ("s5", "s7"),
        ("s5", "s8"), ("s6", "s8"), ("s7", "s9"), ("s8", "s9"),
    ]
    for first, second in links:
        net.addLink(switches[first], switches[second], bw=10, delay="5ms")
    try:
        net.start()
        net.staticArp()
        CLI(net)
    finally:
        net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    build()

