# OptiTransfer — Strict Stop-and-Wait Optical Transfer

This version implements the transfer as a true stop-and-wait protocol:

```text
SENDER DISPLAY
    |
    | DATA #0
    v
RECEIVER CAMERA
    |
    | validate CRC
    v
RECEIVER DISPLAY
    |
    | ACK #0
    v
SENDER CAMERA
    |
    | validate ACK
    v
SENDER DISPLAY
    |
    | DATA #1
    v
...
```

**The sender does not advance to the next DATA packet until it receives the matching ACK.**

If the ACK is not received before the timeout, the same packet is retransmitted.

If the receiver gets a duplicate packet, it does not append it again; it re-displays the ACK for that packet.

## Run

On both laptops:

```bash
python -m venv .venv
```

Windows:
```bash
.venv\Scripts\activate
```

macOS/Linux:
```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
python main.py
```

Laptop A: choose **SEND FILE**.

Laptop B: choose **RECEIVE FILE**.

Both laptops need:
- a display
- a working camera
- camera permission

No Wi-Fi, Bluetooth, Ethernet, Internet, sockets or other network transport is used.

## Important physical arrangement

For full bidirectional ACK:

```text
Laptop A screen  ---> Laptop B camera
Laptop A camera  <--- Laptop B screen
```

The two screens/cameras therefore form two independent optical directions.

## Protocol

Frames:

- START
- DATA
- ACK
- NACK
- END
- FINAL_ACK

Each frame contains a sequence number and CRC32.

For DATA:

```text
sender displays DATA[n]
        ↓
receiver decodes DATA[n]
        ↓
CRC valid?
   yes ─────────> display ACK[n]
   no  ─────────> display NACK[n]
        ↓
sender camera decodes ACK[n]
        ↓
only now:
sender advances to DATA[n+1]
```

## Retry behavior

The sender waits `ack_timeout_s`.

On timeout:

```text
DATA[n] -> timeout -> DATA[n]
```

On NACK:

```text
DATA[n] -> NACK[n] -> DATA[n]
```

The sender retries up to `max_retries`.

The receiver keeps the last successfully accepted sequence and treats a repeated DATA sequence as a duplicate. It re-ACKs the duplicate without writing the payload twice.

## Integrity

- CRC32 validates every optical frame.
- SHA-256 validates the complete reconstructed file.

A file is considered successfully transferred only if the final SHA-256 matches.

## Note about throughput

Stop-and-wait is intentionally slower than streaming many frames, but it is the correct design for your requirement and makes the protocol reliable.

Once this is stable, the project can be upgraded to a sliding-window ARQ protocol for higher throughput.
