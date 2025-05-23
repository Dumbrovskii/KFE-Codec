import os
import sys
import tempfile
import subprocess

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
