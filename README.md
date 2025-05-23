# KFE Codec Prototype

This project contains a minimal reference implementation of a simple codec
capable of storing arbitrary binary data in a visual container format and
restoring it back without loss. The implementation follows the requirements
from the provided technical specification.


The codec stores data as a series of *frames*. Each frame represents a
3840×2160 RGB image where bytes from the input file fill the pixel data in
sequence. Because each pixel contains three bytes, the frame size is
``3840 × 2160 × 3 = 24 883 200`` bytes. Frames are padded with zeroes to reach
this size and are stored sequentially in a custom binary container with a
small header. No compression or encryption is applied.


## Usage

The command line interface supports four operations: `encode`, `decode`,
`capture` and `display`.

```bash
# Encode a binary file to the custom .kfe container
python kfe_codec.py encode input.bin output.kfe

# Decode a previously encoded container back to its original binary form
python kfe_codec.py decode input.kfe restored.bin
```

```bash
# Capture 60 frames from webcam 0 and store in container
python kfe_codec.py capture capture.kfe --device 0 --frames 60

# Display a container in a window or write it to a video file
python kfe_codec.py display capture.kfe --fps 30
```

Use the `-v` option for verbose logging.

## Testing

Unit tests can be executed with `pytest`:

```bash
pytest
```

The tests verify that encoding followed by decoding yields the original data
for both small and multi-frame inputs.

## Dependencies

The CLI relies on `opencv-python` and `numpy` for capture and display
functionality. These packages are not required for basic encoding/decoding but
must be installed to use the `capture` or `display` commands.
