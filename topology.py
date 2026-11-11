from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel


def run():
    net = Mininet(controller=None, switch=OVSSwitch, link=TCLink,
                  autoSetMacs=False)

    net.addController('c0', controller=RemoteController,
                      ip='127.0.0.1', port=6653)

    # Hosts with fixed MACs (the controller relies on these)
    h1 = net.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
    h4 = net.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')

    # Switches (failMode secure = no looping fallback if controller is gone)
    s1 = net.addSwitch('s1', protocols='OpenFlow13', failMode='secure')
    s2 = net.addSwitch('s2', protocols='OpenFlow13', failMode='secure')
    s3 = net.addSwitch('s3', protocols='OpenFlow13', failMode='secure')
    s4 = net.addSwitch('s4', protocols='OpenFlow13', failMode='secure')

    # IMPORTANT: link ORDER decides port numbers. Do not reorder these.
    net.addLink(h1, s1)                                # s1 port 1
    net.addLink(s1, s2, bw=10, delay='5ms')            # s1 port 2, s2 port 1
    net.addLink(s1, s3, bw=10, delay='5ms')            # s1 port 3, s3 port 1
    net.addLink(s2, s4, bw=10, delay='5ms')            # s2 port 2, s4 port 1
    net.addLink(s3, s4, bw=10, delay='5ms')            # s3 port 2, s4 port 2
    net.addLink(h4, s4)                                # s4 port 3

    net.start()
    net.staticArp()   # pre-fill ARP so hosts never broadcast
    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()

