import os
import struct


import pytest

import types
import sys

from kfe_loopback import packet_to_frame, frame_to_packet, run_loopback
from kfe_codec import FRAME_SIZE



class DummyArray:
    def __init__(self, buf=b""):
        self.buf = buf

    def tobytes(self):
        return bytes(self.buf)

    def reshape(self, shape):
        return self



def make_dummy_cv2(frame_bytes):
    """Return a dummy cv2 module delivering ``frame_bytes`` on capture."""

    class DummyCap:
        def __init__(self, device):
            self.device = device

def make_dummy_cv2(frame_bytes, *, frames=1):
    class DummyCap:
        def __init__(self, device):
            self.frame = frame_bytes
            self.frames = frames
            self.count = 0


        def isOpened(self):
            return True

        def read(self):


        def release(self):
            pass

    dummy_cv2 = types.SimpleNamespace(
        VideoCapture=lambda device: DummyCap(device),
        resize=lambda frame, size: frame,
        cvtColor=lambda frame, code: frame,
        COLOR_BGR2RGB=1,
        COLOR_RGB2BGR=2,
        imshow=lambda *a, **k: None,
        waitKey=lambda *a, **k: None,
        destroyAllWindows=lambda: None,
    )
    return dummy_cv2



def test_packet_roundtrip():
    data = b"hello packet"
    frame = packet_to_frame(data)
    assert len(frame) == FRAME_SIZE
    assert frame_to_packet(frame) == data


def test_packet_too_large():
    data = bytes(FRAME_SIZE)
    with pytest.raises(ValueError):
        packet_to_frame(data)


def test_run_loopback(monkeypatch):
    packet = b"demo"
    frame = packet_to_frame(packet)

    # Prepare dummy TUN pipes
    r_in, w_in = os.pipe()
    r_out, w_out = os.pipe()

    os.write(w_in, packet)

    def dummy_open_tun(name):
        return 0

    orig_read = os.read
    orig_write = os.write

    def dummy_read(fd, n):
        return orig_read(r_in, n)

    written = []

    def dummy_write(fd, data):
        written.append(data)
        return orig_write(w_out, data)

    import kfe_loopback as kl
    monkeypatch.setattr(kl, "_open_tun", dummy_open_tun)
    monkeypatch.setattr(kl.os, "read", dummy_read)
    monkeypatch.setattr(kl.os, "write", dummy_write)


    dummy_cv2 = make_dummy_cv2(frame)
    dummy_np = types.SimpleNamespace(frombuffer=lambda buf, dtype: DummyArray(buf))

    monkeypatch.setitem(sys.modules, "cv2", dummy_cv2)
    monkeypatch.setitem(sys.modules, "numpy", dummy_np)

    kl.run_loopback(tun="tun0", device=0, packets=1)

    assert written and written[0] == packet

