import unittest
import struct

from ..protocol import Packet, Opcode

class PacketTest(unittest.TestCase):
    def test_decode(self):
        payload = b"Test payload"
        packet = b"\x00\x15" + struct.pack("!I", len(payload)) + payload
        p = Packet.decode(packet)

        if p == None:
            self.assertIsNotNone(p)
            return

        self.assertEqual(p.opcode, Opcode.Shutdown)
        self.assertEqual(p.version, 0x0)
        self.assertEqual(p.payload, payload)

    def test_encode(self):
        p = Packet(opcode=Opcode.Atr, payload=b"Payload", version=0x0)
        self.assertEqual(p.encode(), b"\x00\x02\x00\x00\x00\x07Payload")

    def test_encode_decode(self):
        def eq(x, y, msg=None):
            if x.version != y.version or x.opcode != y.opcode or x.payload != y.payload:
                self.failureException(msg)

        self.addTypeEqualityFunc(Packet, eq)

        p = Packet(opcode=Opcode.Reset, payload=b"Payload", version=0x0)
        self.assertEqual(p, Packet.decode(p.encode()))
