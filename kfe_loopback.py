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
import logging

from kfe_codec import FRAME_SIZE, WIDTH, HEIGHT, CHANNELS


logger = logging.getLogger(__name__)

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


def run_loopback(tun: str = "tun0", device: int = 0, packets: int = 100) -> None:
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
        os.close(tun_fd)
        raise RuntimeError(f"Unable to open capture device {device}")

    rtts: list[float] = []
    total_bytes = 0
    start_time = time.monotonic()
    try:
        processed = 0
        while processed < packets:
            data = os.read(tun_fd, 65535)
            send_ts = time.monotonic()
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
            os.write(tun_fd, packet)
            recv_ts = time.monotonic()

            rtts.append(recv_ts - send_ts)
            total_bytes += len(packet)
            processed += 1
    finally:
        cap.release()
        cv2.destroyAllWindows()
        os.close(tun_fd)

    total_time = time.monotonic() - start_time
    if rtts and total_time > 0:
        logger.info(
            "Processed %d packets: RTT min/avg/max %.6f/%.6f/%.6f s, throughput %.1f B/s",
            processed,
            min(rtts),
            sum(rtts) / len(rtts),
            max(rtts),
            total_bytes / total_time,
        )
