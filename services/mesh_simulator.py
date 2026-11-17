from typing import Dict, List, Tuple
from pydantic import BaseModel

class MeshPacket(BaseModel):
    packetId: str
    ttl: int
    createdAt: int
    ciphertext: str

class VirtualDevice:
    def __init__(self, device_id: str, has_internet: bool = False):
        self.device_id = device_id
        self.has_internet = has_internet
        self.held_packets: Dict[str, MeshPacket] = {}

    def hold(self, packet: MeshPacket):
        if packet.packetId not in self.held_packets:
            self.held_packets[packet.packetId] = packet

    def clear(self):
        self.held_packets.clear()

class MeshSimulatorService:
    def __init__(self):
        self.devices: Dict[str, VirtualDevice] = {}
        self.seed_default_devices()

    def seed_default_devices(self):
        # 3 offline devices and 2 online bridge devices to exercise concurrency
        self.devices = {
            "phone-alice":    VirtualDevice("phone-alice", False),
            "phone-stranger1": VirtualDevice("phone-stranger1", False),
            "phone-stranger2": VirtualDevice("phone-stranger2", False),
            "phone-bridge1":   VirtualDevice("phone-bridge1", True),
            "phone-bridge2":   VirtualDevice("phone-bridge2", True),
        }

    def inject(self, device_id: str, packet: MeshPacket):
        if device_id in self.devices:
            self.devices[device_id].hold(packet)

    def gossip_once(self) -> Tuple[int, Dict[str, int]]:
        transfers = 0
        device_list = list(self.devices.values())
        snapshot = {d.device_id: list(d.held_packets.values()) for d in device_list}

        for src in device_list:
            for pkt in snapshot[src.device_id]:
                if pkt.ttl <= 0:
                    continue
                for dst in device_list:
                    if dst.device_id == src.device_id:
                        continue
                    if pkt.packetId in dst.held_packets:
                        continue

                    forwarded = MeshPacket(
                        packetId=pkt.packetId,
                        ttl=pkt.ttl - 1,
                        createdAt=pkt.createdAt,
                        ciphertext=pkt.ciphertext
                    )
                    dst.hold(forwarded)
                    transfers += 1

        device_counts = {d.device_id: len(d.held_packets) for d in self.devices.values()}
        return transfers, device_counts

    def collect_bridge_uploads(self) -> List[Tuple[str, MeshPacket]]:
        uploads = []
        for d in self.devices.values():
            if not d.has_internet:
                continue
            for pkt in d.held_packets.values():
                uploads.append((d.device_id, pkt))
        return uploads

    def reset_mesh(self):
        for d in self.devices.values():
            d.clear()