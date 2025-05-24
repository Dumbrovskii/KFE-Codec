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


def make_dummy_cv2(frame_bytes, *, frames=1):
    class DummyCap:
        def __init__(self, device):
            self.frame = frame_bytes
            self.frames = frames
            self.count = 0

        def isOpened(self):
            return True

        def read(self):
            if self.count >= self.frames:
                return False, None
            self.count += 1
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

    dummy_cv2 = make_dummy_cv2(frame, frames=2)
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


def test_run_loopback_metrics(monkeypatch, capsys):
    packet = b"ab"
    frame = packet_to_frame(packet)

    written = []

    def fake_read(fd, n):
        return packet

    def fake_write(fd, data):
        written.append(data)

    def fake_close(fd):
        pass

    dummy_cv2 = make_dummy_cv2(frame, frames=2)
    dummy_np = types.SimpleNamespace(frombuffer=lambda buf, dtype: DummyArray(buf))

    monkeypatch.setitem(sys.modules, "cv2", dummy_cv2)
    monkeypatch.setitem(sys.modules, "numpy", dummy_np)
    monkeypatch.setattr("kfe_loopback._open_tun", lambda name: 1)

    times = [0.0, 1.0, 1.2, 2.0, 2.5, 3.0]
    def fake_monotonic():
        return times.pop(0) if times else 3.0
    monkeypatch.setattr("kfe_loopback.time.monotonic", fake_monotonic)

    run_loopback(
        tun="tun0",
        device=0,
        packets=2,
        os_read=fake_read,
        os_write=fake_write,
        os_close=fake_close,
        periodic=False,
    )

    out = capsys.readouterr().out.strip().splitlines()[-1]
    assert written == [packet, packet]
    assert "Processed: 2 packets" in out
    assert "RTT min/avg/max: 0.2000/0.3500/0.5000 s" in out
    assert "Throughput: 1.33 B/s" in out


def test_run_loopback_periodic(monkeypatch, capsys):
    packet = b"x"
    frame = packet_to_frame(packet)

    def fake_read(fd, n):
        return packet

    def fake_write(fd, data):
        pass

    def fake_close(fd):
        pass

    dummy_cv2 = make_dummy_cv2(frame)
    dummy_np = types.SimpleNamespace(frombuffer=lambda buf, dtype: DummyArray(buf))

    monkeypatch.setitem(sys.modules, "cv2", dummy_cv2)
    monkeypatch.setitem(sys.modules, "numpy", dummy_np)
    monkeypatch.setattr("kfe_loopback._open_tun", lambda name: 1)

    times = [0.0, 1.0, 1.1, 2.0, 2.1, 3.0]
    def fake_monotonic():
        return times.pop(0) if times else 3.0
    monkeypatch.setattr("kfe_loopback.time.monotonic", fake_monotonic)

    run_loopback(
        tun="tun0",
        device=0,
        packets=2,
        os_read=fake_read,
        os_write=fake_write,
        os_close=fake_close,
        periodic=True,
    )

    out_lines = capsys.readouterr().out.strip().splitlines()
    assert len(out_lines) == 3  # two periodic + final
    assert "Processed: 1 packets" in out_lines[0]
    assert "Processed: 2 packets" in out_lines[-1]


def test_run_loopback_pipe(monkeypatch, capsys):
    packet = b"pipe"
    frame = b"f" + packet

    r_fd, w_fd = os.pipe()
    os.write(w_fd, packet)

    dummy_cv2 = make_dummy_cv2(frame)
    dummy_np = types.SimpleNamespace(frombuffer=lambda buf, dtype: DummyArray(buf))

    monkeypatch.setitem(sys.modules, "cv2", dummy_cv2)
    monkeypatch.setitem(sys.modules, "numpy", dummy_np)

    monkeypatch.setattr("kfe_loopback._open_tun", lambda name: r_fd)
    monkeypatch.setattr("kfe_loopback.packet_to_frame", lambda pkt: b"f" + pkt)
    monkeypatch.setattr("kfe_loopback.frame_to_packet", lambda fr: fr[1:])

    times = [0.0, 1.0, 1.2, 2.0]

    def fake_monotonic():
        return times.pop(0)

    monkeypatch.setattr("kfe_loopback.time.monotonic", fake_monotonic)

    written = []

    def os_read(fd, n):
        return os.read(r_fd, n)

    def os_write(fd, data):
        written.append(data)
        return os.write(w_fd, data)

    def os_close(fd):
        os.close(r_fd)
        os.close(w_fd)

    run_loopback(
        tun="tun0",
        device=0,
        packets=1,
        os_read=os_read,
        os_write=os_write,
        os_close=os_close,
    )

    out = capsys.readouterr().out.strip().splitlines()[-1]
    assert written == [packet]
    assert "Processed: 1 packets" in out
    assert "Throughput" in out

