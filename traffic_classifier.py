from pox.core import core
from pox.lib.util import dpid_to_str
from pox.lib.packet import ethernet, ipv4, tcp, udp, icmp
import pox.openflow.libopenflow_01 as of
from pox.lib.addresses import IPAddr
import time

log = core.getLogger()


class TrafficClassifier(object):
    def __init__(self):
        core.openflow.addListeners(self)
        self.mac_to_port = {}

        # Traffic statistics
        self.stats = {
            'TCP': 0,
            'UDP': 0,
            'ICMP': 0,
            'OTHER': 0
        }
        self.total_packets = 0
        self.start_time = time.time()
        self.packet_log = []

        # Periodic stats display
        from pox.lib.recoco import Timer
        Timer(10, self._display_stats, recurring=True)

    def _display_stats(self):
        """Display traffic classification results and distribution."""
        elapsed = time.time() - self.start_time
        log.info("=" * 60)
        log.info("TRAFFIC CLASSIFICATION REPORT")
        log.info("=" * 60)
        log.info("Elapsed time: %.2f seconds" % elapsed)
        log.info("Total packets classified: %d" % self.total_packets)
        log.info("-" * 40)

        for proto, count in self.stats.items():
            if self.total_packets > 0:
                percentage = (count / self.total_packets) * 100
            else:
                percentage = 0.0
            log.info("  %-8s : %5d packets  (%6.2f%%)" % (proto, count, percentage))

        log.info("-" * 40)

        if self.packet_log:
            log.info("Last 5 classified packets:")
            for entry in self.packet_log[-5:]:
                log.info("  %s" % entry)

        log.info("=" * 60)

    def _classify_packet(self, packet, ip_packet, in_port, dpid):
        """Classify packet by protocol and update statistics."""
        protocol = 'OTHER'
        src_ip = str(ip_packet.srcip)
        dst_ip = str(ip_packet.dstip)

        tcp_pkt = ip_packet.find('tcp')
        udp_pkt = ip_packet.find('udp')
        icmp_pkt = ip_packet.find('icmp')

        if tcp_pkt is not None:
            protocol = 'TCP'
            log_entry = (
                "[TCP]  %s:%d -> %s:%d  (Switch: %s, Port: %d)"
                % (src_ip, tcp_pkt.srcport, dst_ip, tcp_pkt.dstport, dpid, in_port)
            )
        elif udp_pkt is not None:
            protocol = 'UDP'
            log_entry = (
                "[UDP]  %s:%d -> %s:%d  (Switch: %s, Port: %d)"
                % (src_ip, udp_pkt.srcport, dst_ip, udp_pkt.dstport, dpid, in_port)
            )
        elif icmp_pkt is not None:
            protocol = 'ICMP'
            log_entry = (
                "[ICMP] %s -> %s  Type: %d, Code: %d  (Switch: %s, Port: %d)"
                % (src_ip, dst_ip, icmp_pkt.type, icmp_pkt.code, dpid, in_port)
            )
        else:
            log_entry = (
                "[OTHER] %s -> %s  Proto: %d  (Switch: %s, Port: %d)"
                % (src_ip, dst_ip, ip_packet.protocol, dpid, in_port)
            )

        self.stats[protocol] += 1
        self.total_packets += 1
        self.packet_log.append(log_entry)
        log.info("Classified: %s" % log_entry)

        return protocol

    def _handle_ConnectionUp(self, event):
        """Handle new switch connection."""
        log.info("Switch %s connected." % dpid_to_str(event.dpid))

    def _handle_PacketIn(self, event):
        """Handle packet_in events: classify, learn MAC, install flow, forward."""
        packet = event.parsed
        if not packet.parsed:
            log.warning("Ignoring incomplete packet")
            return

        dpid = dpid_to_str(event.dpid)
        in_port = event.port

        # MAC learning
        if dpid not in self.mac_to_port:
            self.mac_to_port[dpid] = {}
        self.mac_to_port[dpid][str(packet.src)] = in_port

        # Classify IP packets
        ip_pkt = packet.find('ipv4')
        if ip_pkt is not None:
            protocol = self._classify_packet(packet, ip_pkt, in_port, dpid)
        else:
            protocol = None

        # Determine output port
        if str(packet.dst) in self.mac_to_port.get(dpid, {}):
            out_port = self.mac_to_port[dpid][str(packet.dst)]
        else:
            out_port = of.OFPP_ALL

        # Install flow rules for classified IP traffic
        if out_port != of.OFPP_ALL and ip_pkt is not None:
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match()
            msg.match.dl_type = 0x0800
            msg.match.in_port = in_port

            if protocol == 'TCP':
                tcp_pkt = ip_pkt.find('tcp')
                msg.match.nw_proto = 6
                msg.match.nw_src = ip_pkt.srcip
                msg.match.nw_dst = ip_pkt.dstip
                msg.match.tp_src = tcp_pkt.srcport
                msg.match.tp_dst = tcp_pkt.dstport
                msg.priority = 30
            elif protocol == 'UDP':
                udp_pkt = ip_pkt.find('udp')
                msg.match.nw_proto = 17
                msg.match.nw_src = ip_pkt.srcip
                msg.match.nw_dst = ip_pkt.dstip
                msg.match.tp_src = udp_pkt.srcport
                msg.match.tp_dst = udp_pkt.dstport
                msg.priority = 30
            elif protocol == 'ICMP':
                msg.match.nw_proto = 1
                msg.match.nw_src = ip_pkt.srcip
                msg.match.nw_dst = ip_pkt.dstip
                msg.priority = 20
            else:
                msg.match.nw_src = ip_pkt.srcip
                msg.match.nw_dst = ip_pkt.dstip
                msg.priority = 10

            msg.idle_timeout = 30
            msg.hard_timeout = 60
            msg.actions.append(of.ofp_action_output(port=out_port))
            event.connection.send(msg)

        # Forward the current packet
        msg = of.ofp_packet_out()
        msg.data = event.ofp
        msg.in_port = in_port
        action = of.ofp_action_output(port=out_port)
        msg.actions.append(action)
        event.connection.send(msg)


def launch():
    core.registerNew(TrafficClassifier)
    log.info("Traffic Classifier started.")