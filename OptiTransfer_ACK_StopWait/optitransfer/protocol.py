import struct
import zlib
from enum import IntEnum

MAGIC = b"OPT5"
VERSION = 1

# magic, version, type, flags, reserved, sequence, total
HEADER = struct.Struct(">4sBBBBII")
U32 = struct.Struct(">I")

class FrameType(IntEnum):
    START = 1
    DATA = 2
    ACK = 3
    NACK = 4
    END = 5
    FINAL_ACK = 6

def pack_frame(frame_type, sequence, total, payload=b"", flags=0):
    payload = bytes(payload)
    header = HEADER.pack(
        MAGIC, VERSION, int(frame_type), flags & 0xFF,
        0, int(sequence), int(total)
    )
    body = header + U32.pack(len(payload)) + payload
    crc = U32.pack(zlib.crc32(body) & 0xffffffff)
    return body + crc

def unpack_frame(raw):
    if raw is None or len(raw) < HEADER.size + 8:
        return None

    try:
        magic, version, ftype, flags, reserved, sequence, total = HEADER.unpack(
            raw[:HEADER.size]
        )
        payload_len = U32.unpack(
            raw[HEADER.size:HEADER.size + 4]
        )[0]
    except struct.error:
        return None

    if magic != MAGIC or version != VERSION:
        return None

    payload_start = HEADER.size + 4
    payload_end = payload_start + payload_len

    if payload_end + 4 > len(raw):
        return None

    body = raw[:payload_end]
    received_crc = U32.unpack(raw[payload_end:payload_end + 4])[0]

    if (zlib.crc32(body) & 0xffffffff) != received_crc:
        return None

    try:
        frame_type = FrameType(ftype)
    except ValueError:
        return None

    return {
        "type": frame_type,
        "flags": flags,
        "sequence": sequence,
        "total": total,
        "payload": raw[payload_start:payload_end],
    }
