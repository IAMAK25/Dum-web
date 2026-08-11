from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    board_size: int = 900
    cols: int = 40
    rows: int = 30

    camera_index: int = 0
    camera_width: int = 1280
    camera_height: int = 720

    # How long each optical frame remains visible.
    frame_hold_s: float = 0.35

    # Sender waits this long for an ACK/NACK.
    ack_timeout_s: float = 3.0

    # Maximum retransmissions for one packet.
    max_retries: int = 8

    # Number of consecutive identical decodes needed before accepting
    # a new optical frame. This reduces screen/camera transition errors.
    stable_frames: int = 2

    min_board_fraction: float = 0.10
    max_board_fraction: float = 0.98

    camera_poll_delay_ms: int = 20

CONFIG = Config()
