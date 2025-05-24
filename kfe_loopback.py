"""Utilities for transmitting network packets via KFE frames.

This module implements helper functions used in the loopback prototype.
Packets are packed into a single KFE frame by prefixing them with their
length. The frame is padded with zeroes to reach the fixed size expected by
:mod:`kfe_codec`.
"""

from __future__ import annotations

import os
import struct

import time
from typing import List
from typing import Generator


from kfe_codec import FRAME_SIZE, WIDTH, HEIGHT, CHANNELS

__all__ = ["packet_to_frame", "frame_to_packet", "run_loopback"]


def packet_to_frame(packet: bytes) -> bytes:
    """Return a byte sequence representing a KFE frame for ``packet``.

    The frame layout is::

        +---------+---------------------+
        | length  | packet data [...]   |
        +---------+---------------------+
        | padding up to FRAME_SIZE      |
        +-------------------------------+

    Parameters
    ----------
    packet:
        Raw network packet. Its size must not exceed ``FRAME_SIZE - 4``.

    Returns
    -------
    bytes
        A bytes object of exactly ``FRAME_SIZE`` bytes containing the packet.
    """
    if len(packet) > FRAME_SIZE - 4:
        raise ValueError("Packet too large for a single frame")

    header = struct.pack("<I", len(packet))
    padding = FRAME_SIZE - 4 - len(packet)
    return header + packet + bytes(padding)


def frame_to_packet(frame: bytes) -> bytes:
    """Extract a packet from a frame created by :func:`packet_to_frame`."""
    if len(frame) != FRAME_SIZE:
        raise ValueError("Invalid frame length")

    length = struct.unpack("<I", frame[:4])[0]
    if length > FRAME_SIZE - 4:
        raise ValueError("Corrupted frame header")

    return frame[4 : 4 + length]


# Constants used by ``run_loopback`` to configure a TUN interface.
TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000


def _open_tun(name: str) -> int:
    """Create or attach to a TUN interface.

    The caller must have sufficient privileges (usually root). The returned
    file descriptor can be used for reading packets from the interface and
    writing them back.
    """
    import fcntl

    tun_fd = os.open("/dev/net/tun", os.O_RDWR)
    ifr = struct.pack("16sH", name.encode(), IFF_TUN | IFF_NO_PI)
    fcntl.ioctl(tun_fd, TUNSETIFF, ifr)
    return tun_fd



def run_loopback(
    tun: str = "tun0",
    device: int = 0,
    packets: int = 100,
    *,
    os_read=os.read,
    os_write=os.write,
    os_close=os.close,
) -> None:

    """Simple loopback demo using a TUN interface and HDMI capture.

    The function reads packets from ``tun``, converts them to frames using
    :func:`packet_to_frame` and displays them with ``OpenCV``. The same frames
    are captured back from ``device`` and decoded with :func:`frame_to_packet`.
    Decoded packets are written back to the TUN interface.

    Parameters
    ----------
    tun:
        Name of the existing TUN interface (e.g. ``"tun0"``).
    device:
        Index of the capture device (the HDMI grabber in loopback setup).
    packets:
        Maximum number of packets to process. The function exits after this
        many packets have been handled.
    """

    import cv2
    import numpy as np

    tun_fd = _open_tun(tun)

    cap = cv2.VideoCapture(device)
    if not cap.isOpened():

        os_close(tun_fd)
        raise RuntimeError(f"Unable to open capture device {device}")

    try:
        rtts: List[float] = []
        bytes_total = 0
        start_time = time.time()
        processed = 0
        while processed < packets:
            send_ts = time.time()
            data = os_read(tun_fd, 65535)

            frame_bytes = packet_to_frame(data)

            arr = (
                np.frombuffer(frame_bytes, dtype="uint8")
                .reshape((HEIGHT, WIDTH, CHANNELS))
            )
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            cv2.imshow("kfe-loopback", arr)
            cv2.waitKey(1)

            ret, received = cap.read()
            if not ret:
                continue
            received = cv2.resize(received, (WIDTH, HEIGHT))
            received = cv2.cvtColor(received, cv2.COLOR_BGR2RGB)
            packet = frame_to_packet(received.tobytes())

            os_write(tun_fd, packet)
            rtts.append(time.time() - send_ts)
            bytes_total += len(packet)
            processed += 1

        elapsed = time.time() - start_time
        if rtts:
            rtt_min = min(rtts)
            rtt_avg = sum(rtts) / len(rtts)
            rtt_max = max(rtts)
        else:
            rtt_min = rtt_avg = rtt_max = 0.0
        throughput = bytes_total / elapsed if elapsed > 0 else 0.0

        print(
            f"Processed: {processed} packets | "
            f"RTT min/avg/max: {rtt_min:.4f}/{rtt_avg:.4f}/{rtt_max:.4f} s | "
            f"Throughput: {throughput:.2f} B/s"
        )
    finally:
        cap.release()
        cv2.destroyAllWindows()
        os_close(tun_fd)

