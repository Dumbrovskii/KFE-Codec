# KFE Codec Prototype

This project contains a minimal reference implementation of a simple codec
capable of storing arbitrary binary data in a visual container format and
restoring it back without loss. The implementation follows the requirements
from the provided technical specification.


The codec stores data as a series of *frames*. Each frame represents a
3840×2160 image with **three bytes per pixel**. The implementation uses an
RGB layout, so every pixel consists of red, green, and blue components.
Because each pixel contains three bytes, the frame size is ``3840 × 2160 × 3 =
24 883 200`` bytes. Frames are padded with zeroes to reach this size and are
stored sequentially in a custom binary container with a small header. No
compression or encryption is applied.


## Usage

The command line interface supports several operations: `encode`, `decode`,
`capture`, `display` and `loopback`.

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

# Forward network packets through HDMI loopback using tun0
python kfe_codec.py loopback --tun tun0 --device 0 --packets 100
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

## Loopback demonstration

The `kfe_loopback` module provides helper functions for packing network
packets into KFE frames. It also contains a simple `run_loopback()` routine
that demonstrates how a TUN interface can be bridged through an HDMI capture
device. The function requires root privileges to create/attach to the TUN
interface and an accessible video capture device.


### Preparing a TUN interface

On Linux the following commands create a TUN device named ``tun0`` and assign
an address to it (root privileges required):

```bash
sudo ip tuntap add dev tun0 mode tun
sudo ip addr add 10.0.0.1/24 dev tun0
sudo ip link set tun0 up
```

After the interface is created, packets sent to ``tun0`` can be forwarded
through the HDMI loopback using either the Python API above or the CLI
command. The loopback routine prints measured round-trip time (RTT) and
throughput statistics after processing the requested number of packets:

```bash
python kfe_codec.py loopback --tun tun0 --device 0 --packets 100
```


```python
from kfe_loopback import run_loopback

# Forward up to 100 packets through HDMI using tun0 and device 0
run_loopback(tun="tun0", device=0, packets=100)
```

`packet_to_frame()` and `frame_to_packet()` can be used independently of the
loopback demo:

```python
from kfe_loopback import packet_to_frame, frame_to_packet

frame = packet_to_frame(b"demo packet")
packet = frame_to_packet(frame)
```
