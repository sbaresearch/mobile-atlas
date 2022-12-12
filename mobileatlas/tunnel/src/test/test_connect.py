import unittest

from ..connect import IdentifierType, Method, Status, ConnectRequest, ConnectResponse, Imsi, Iccid

class ConnectRequestTest(unittest.TestCase):
    def test_decode(self):
        packet = b"\x00\x01\x00\x00\x00\x05TOKEN\x00IMSIISMI"
        req = ConnectRequest.decode(packet)

        if req == None:
            self.assertIsNotNone(req)
            return

        self.assertNotEqual(req, None)
        self.assertEqual(req.version, 0x0)
        self.assertEqual(req.ident_type, IdentifierType.Imsi)
        self.assertEqual(req.identifier.encoded_len(), 0x8)
        self.assertEqual(req.identifier.imsi, b"IMSIISMI")
        self.assertEqual(req.method, Method.Bearer)
        self.assertEqual(len(req.auth), 0x5)
        self.assertEqual(req.auth, b"TOKEN")

    def test_encode(self):
        cr = ConnectRequest(
                version=0x0,
                ident_type=IdentifierType.Imsi,
                identifier=Imsi(b"imsiIMSI"),
                method=Method.Bearer,
                auth=b"Auth")
        encoded = cr.encode()
        self.assertEqual(encoded, b"\x00\x01\x00\x00\x00\x04Auth\x00imsiIMSI")

    def test_encode_decode(self):
        def eq(x, y, msg=None):
            if x.version != y.version or \
               x.ident_type != y.ident_type or \
               x.identifier != y.identifier or \
               x.method != y.method or \
               x.auth != y.auth:
                self.failureException(msg)

        self.addTypeEqualityFunc(ConnectRequest, eq)
        cr = ConnectRequest(
                version=0x0,
                ident_type=IdentifierType.Iccid,
                identifier=Iccid(b"A" * 0xff),
                method=Method.Bearer,
                auth=b"B" * 2048)
        cr2 = ConnectRequest.decode(cr.encode())

        self.assertEqual(cr, cr2)

class ConnectResponseTest(unittest.TestCase):
    def test_decode(self):
        packet = b"\x00\x00"
        cr = ConnectResponse.decode(packet)

        if cr == None:
            self.assertIsNotNone(cr)
            return

        self.assertEqual(cr.version, 0x0)
        self.assertEqual(cr.status, Status.Success)

    def test_encode(self):
        cr = ConnectResponse(version=0x0, status=Status.MethodError)
        encoded = cr.encode()
        self.assertEqual(encoded, b"\x00\x01")

    def test_encode_decode(self):
        def eq(x, y, msg=None):
            if x.version != y.version or x.status != y.status:
                self.failureException(msg)

        self.addTypeEqualityFunc(ConnectResponse, eq)

        cr = ConnectResponse(version=0x0, status=Status.MethodError)
        cr2 = ConnectResponse.decode(cr.encode())

        self.assertEqual(cr, cr2)
        

if __name__ == "__main__":
    unittest.main()
