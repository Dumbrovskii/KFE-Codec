"""Simple binary <-> KFE codec implementation.

This module provides functions to encode arbitrary binary data into a

visual KFE container format and decode it back. The format stores data
in frames of 3840x2160 RGB pixels (three bytes per pixel).

"""

import argparse
import logging
import math
import os
import struct
from typing import BinaryIO

# Constants for frame size
WIDTH = 3840
HEIGHT = 2160

CHANNELS = 3  # RGB
FRAME_SIZE = WIDTH * HEIGHT * CHANNELS  # bytes per frame

# Header format for the container
# magic(4s) width(uint32) height(uint32) channels(uint32) data_size(uint64) frame_count(uint32)
HEADER_FORMAT = '<4sIIIQI'

HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAGIC = b'KFE0'

logger = logging.getLogger(__name__)


def _write_header(out: BinaryIO, data_size: int, frame_count: int) -> None:

    header = struct.pack(
        HEADER_FORMAT, MAGIC, WIDTH, HEIGHT, CHANNELS, data_size, frame_count
    )

    out.write(header)


def _read_header(inp: BinaryIO):
    header_data = inp.read(HEADER_SIZE)
    if len(header_data) != HEADER_SIZE:
        raise ValueError('Incomplete KFE header')

    magic, width, height, channels, data_size, frame_count = struct.unpack(
        HEADER_FORMAT, header_data
    )
    if (
        magic != MAGIC
        or width != WIDTH
        or height != HEIGHT
        or channels != CHANNELS
    ):

        raise ValueError('Invalid KFE file')
    return data_size, frame_count


def encode(input_path: str, output_path: str) -> None:

    """Encode a binary file into KFE format."""

    logger.info('Encoding %s to %s', input_path, output_path)
    data_size = os.path.getsize(input_path)
    frame_count = math.ceil(data_size / FRAME_SIZE)
    logger.debug('Input size: %d bytes, frames: %d', data_size, frame_count)

    with open(input_path, 'rb') as fin, open(output_path, 'wb') as fout:
        _write_header(fout, data_size, frame_count)
        while True:
            chunk = fin.read(FRAME_SIZE)
            if not chunk:
                break
            if len(chunk) < FRAME_SIZE:
                chunk += bytes(FRAME_SIZE - len(chunk))
            fout.write(chunk)
    logger.info('Encoding complete')


def decode(input_path: str, output_path: str) -> None:

    """Decode a KFE file back into its original binary form."""

    logger.info('Decoding %s to %s', input_path, output_path)
    with open(input_path, 'rb') as fin:
        data_size, frame_count = _read_header(fin)
        logger.debug('Output size: %d bytes, frames: %d', data_size, frame_count)
        remaining = data_size
        with open(output_path, 'wb') as fout:
            for _ in range(frame_count):
                frame = fin.read(FRAME_SIZE)
                if len(frame) < FRAME_SIZE:
                    raise ValueError('Incomplete frame data')
                to_write = frame if remaining >= FRAME_SIZE else frame[:remaining]
                fout.write(to_write)
                remaining -= len(to_write)
            if remaining != 0:
                raise ValueError('Data size mismatch')
    logger.info('Decoding complete')


def capture(output_path: str, *, device: int = 0, frames: int = 30) -> None:
    """Capture frames from a video device and store them in KFE format."""

    import cv2

    logger.info('Capturing %d frame(s) from device %d to %s', frames, device, output_path)
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        raise RuntimeError(f'Unable to open capture device {device}')

    try:
        with open(output_path, 'wb') as fout:
            _write_header(fout, FRAME_SIZE * frames, frames)
            captured = 0
            while captured < frames:
                ret, frame = cap.read()
                if not ret:
                    logger.warning('Capture failed at frame %d', captured)
                    break
                frame = cv2.resize(frame, (WIDTH, HEIGHT))
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                data = frame.tobytes()
                fout.write(data)
                captured += 1

            for _ in range(captured, frames):
                fout.write(bytes(FRAME_SIZE))
    finally:  # ensure device released
        cap.release()

    logger.info('Capture complete')


def display(
    input_path: str,
    *,
    output: str | None = None,
    fps: int = 30,
    window: str = 'KFE Display',
) -> None:
    """Display a KFE container or optionally write it to a video file."""

    import cv2
    import numpy as np

    logger.info('Displaying %s', input_path)
    with open(input_path, 'rb') as fin:
        _data_size, frame_count = _read_header(fin)
        writer = None
        if output:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(output, fourcc, fps, (WIDTH, HEIGHT))
        for _ in range(frame_count):
            frame_bytes = fin.read(FRAME_SIZE)
            if len(frame_bytes) < FRAME_SIZE:
                raise ValueError('Incomplete frame data')
            arr = np.frombuffer(frame_bytes, dtype='uint8').reshape((HEIGHT, WIDTH, CHANNELS))
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            if writer:
                writer.write(arr)
            else:
                cv2.imshow(window, arr)
                cv2.waitKey(int(1000 / fps))

        if writer:
            writer.release()
        else:
            cv2.destroyAllWindows()
    logger.info('Display complete')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Simple binary <-> KFE codec')
    subparsers = parser.add_subparsers(dest='command', required=True)

    enc = subparsers.add_parser('encode', help='Encode binary file to KFE')
    enc.add_argument('input', help='Input binary file')
    enc.add_argument('output', help='Output KFE file')

    dec = subparsers.add_parser('decode', help='Decode KFE file to binary')
    dec.add_argument('input', help='Input KFE file')
    dec.add_argument('output', help='Output binary file')

    cap_cmd = subparsers.add_parser('capture', help='Capture from video device to KFE')
    cap_cmd.add_argument('output', help='Output KFE file')
    cap_cmd.add_argument('--device', type=int, default=0, help='Capture device ID')
    cap_cmd.add_argument('--frames', type=int, default=30, help='Number of frames to capture')

    disp = subparsers.add_parser('display', help='Display KFE container')
    disp.add_argument('input', help='Input KFE file')
    disp.add_argument('--output', help='Optional video output file')
    disp.add_argument('--fps', type=int, default=30, help='Frames per second')
    disp.add_argument('--window', default='KFE Display', help='Display window name')

    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='%(levelname)s: %(message)s')

    if args.command == 'encode':
        encode(args.input, args.output)
    elif args.command == 'decode':
        decode(args.input, args.output)
    elif args.command == 'capture':
        capture(args.output, device=args.device, frames=args.frames)
    elif args.command == 'display':
        display(args.input, output=args.output, fps=args.fps, window=args.window)


if __name__ == '__main__':
    main()
