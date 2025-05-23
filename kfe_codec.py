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


def main(argv=None):
    parser = argparse.ArgumentParser(description='Simple binary <-> KFE codec')
    subparsers = parser.add_subparsers(dest='command', required=True)

    enc = subparsers.add_parser('encode', help='Encode binary file to KFE')
    enc.add_argument('input', help='Input binary file')
    enc.add_argument('output', help='Output KFE file')

    dec = subparsers.add_parser('decode', help='Decode KFE file to binary')
    dec.add_argument('input', help='Input KFE file')
    dec.add_argument('output', help='Output binary file')

    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='%(levelname)s: %(message)s')

    if args.command == 'encode':
        encode(args.input, args.output)
    elif args.command == 'decode':
        decode(args.input, args.output)


if __name__ == '__main__':
    main()
