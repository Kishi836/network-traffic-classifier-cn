from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import TCLink


class TrafficClassifierTopo(Topo):
    """Custom topology: 1 switch, 4 hosts for traffic classification testing."""

    def build(self):
        # Add switch (OpenFlow 1.0 for POX compatibility)
        s1 = self.addSwitch('s1')

        # Add 4 hosts
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')
        h3 = self.addHost('h3', ip='10.0.0.3/24')
        h4 = self.addHost('h4', ip='10.0.0.4/24')

        # Connect hosts to switch
        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)
        self.addLink(h4, s1)


def run():
    setLogLevel('info')
    topo = TrafficClassifierTopo()
    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6633),
        switch=OVSSwitch,
        link=TCLink
    )

    net.start()
    print("\n*** Traffic Classification Topology ***")
    print("Hosts: h1 (10.0.0.1), h2 (10.0.0.2), h3 (10.0.0.3), h4 (10.0.0.4)")
    print("Switch: s1 (OpenFlow 1.0)")
    print("Controller: POX @ 127.0.0.1:6633")
    print("\n*** Test Commands ***")
    print("ICMP:  h1 ping h2")
    print("TCP:   h1 iperf h2")
    print("UDP:   h1 iperf -u h2")
    print("*" * 50)

    CLI(net)
    net.stop()


if __name__ == '__main__':
    run()