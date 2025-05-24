import os
import struct

import sys
import types

import pytest

from kfe_loopback import packet_to_frame, frame_to_packet, run_loopback

from kfe_codec import FRAME_SIZE


def test_packet_roundtrip():
    data = b"hello packet"
    frame = packet_to_frame(data)
    assert len(frame) == FRAME_SIZE
    assert frame_to_packet(frame) == data


def test_packet_too_large():
    data = bytes(FRAME_SIZE)
    with pytest.raises(ValueError):
        packet_to_frame(data)


class DummyArray:
    def __init__(self, buf=b""):
        self.buf = buf

    def tobytes(self):
        return bytes(self.buf)

    def reshape(self, shape):
        return self


def make_dummy_cv2(frame_bytes):
    class DummyCap:
        def __init__(self, device):
            self.frame = frame_bytes
            self.used = False

        def isOpened(self):
            return True

        def read(self):
            if self.used:
                return False, None
            self.used = True
            return True, DummyArray(self.frame)

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


def test_run_loopback(monkeypatch):
    packet = b"net"
    frame = packet_to_frame(packet)

    written = []

    def fake_read(fd, n):
        return packet

    def fake_write(fd, data):
        written.append(data)

    def fake_close(fd):
        pass

    dummy_cv2 = make_dummy_cv2(frame)
    dummy_np = types.SimpleNamespace(frombuffer=lambda buf, dtype: DummyArray(buf))

    monkeypatch.setitem(sys.modules, "cv2", dummy_cv2)
    monkeypatch.setitem(sys.modules, "numpy", dummy_np)
    monkeypatch.setattr("kfe_loopback._open_tun", lambda name: 1)

    run_loopback(
        tun="tun0",
        device=0,
        packets=1,
        os_read=fake_read,
        os_write=fake_write,
        os_close=fake_close,
    )

    assert written == [packet]

