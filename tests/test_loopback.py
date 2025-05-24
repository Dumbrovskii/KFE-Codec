import os
import struct

import pytest

from kfe_loopback import packet_to_frame, frame_to_packet
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
