import os
import sys
import tempfile
import subprocess
import types

import pytest

# Ensure the module can be imported when tests run from different locations
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kfe_codec import encode, decode, FRAME_SIZE


def roundtrip(data: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 'src.bin')
        enc = os.path.join(tmp, 'out.kfe')
        dst = os.path.join(tmp, 'dst.bin')
        with open(src, 'wb') as f:
            f.write(data)
        encode(src, enc)
        decode(enc, dst)
        with open(dst, 'rb') as f:
            return f.read()


def test_roundtrip_small():
    data = b'hello world' * 10
    assert roundtrip(data) == data


def test_roundtrip_multi_frame():
    data = os.urandom(FRAME_SIZE + 123)
    assert roundtrip(data) == data


def test_cli():
    data = b'cli test data'
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 's.bin')
        enc = os.path.join(tmp, 'o.kfe')
        dst = os.path.join(tmp, 'd.bin')
        with open(src, 'wb') as f:
            f.write(data)
        subprocess.check_call(['python', 'kfe_codec.py', 'encode', src, enc])
        subprocess.check_call(['python', 'kfe_codec.py', 'decode', enc, dst])
        with open(dst, 'rb') as f:
            assert f.read() == data


class DummyArray:
    def __init__(self, buf=b""):
        self.buf = buf

    def tobytes(self):
        return bytes(self.buf)

    def reshape(self, shape):
        return self


def make_dummy_cv2(frames_to_capture=1, stored_frames=None):
    """Return a dummy cv2 module for testing."""

    if stored_frames is None:
        stored_frames = [bytes(FRAME_SIZE) for _ in range(frames_to_capture)]
    else:
        stored_frames = list(stored_frames)

    class DummyCap:
        def __init__(self, device):
            self.device = device
            self.index = 0

        def isOpened(self):
            return True

        def read(self):
            if self.index >= len(stored_frames):
                return False, None
            buf = stored_frames[self.index]
            self.index += 1
            return True, DummyArray(buf)

        def release(self):
            pass

    class DummyWriter:
        def __init__(self):
            self.written = []

        def write(self, frame):
            self.written.append(frame)

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
        VideoWriter_fourcc=lambda *a: 0,
        VideoWriter=lambda *a, **k: DummyWriter(),
    )
    return dummy_cv2


def test_capture_command(monkeypatch, tmp_path):
    import types
    import kfe_codec

    dummy_cv2 = make_dummy_cv2(frames_to_capture=2)
    monkeypatch.setitem(sys.modules, 'cv2', dummy_cv2)

    out = tmp_path / 'cap.kfe'
    kfe_codec.main(['capture', str(out), '--frames', '2', '--device', '1'])

    with open(out, 'rb') as f:
        _size, count = kfe_codec._read_header(f)
    assert count == 2


def test_display_command(monkeypatch, tmp_path):
    import types
    import kfe_codec

    data = b'x' * 100
    with tempfile.TemporaryDirectory() as tmpdir:
        src = os.path.join(tmpdir, 's.bin')
        enc = os.path.join(tmpdir, 'c.kfe')
        with open(src, 'wb') as f:
            f.write(data)
        encode(src, enc)

        dummy_cv2 = make_dummy_cv2()
        monkeypatch.setitem(sys.modules, 'cv2', dummy_cv2)
        dummy_np = types.SimpleNamespace(
            frombuffer=lambda buf, dtype: DummyArray(buf)
        )
        monkeypatch.setitem(sys.modules, 'numpy', dummy_np)

        kfe_codec.main(['display', enc, '--fps', '1'])

