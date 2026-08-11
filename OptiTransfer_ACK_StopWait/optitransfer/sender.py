import os
import time
import cv2

from .camera import Camera
from .integrity import sha256_file
from .optical import OpticalCodec
from .protocol import FrameType, pack_frame
from .stopwait import StopAndWaitEndpoint

class Sender:
    def __init__(self, cfg):
        self.cfg = cfg
        self.codec = OpticalCodec(cfg)
        self.camera = Camera(cfg)
        self.endpoint = StopAndWaitEndpoint(
            cfg, self.codec, self.camera
        )

    def run(self, path):
        if not os.path.isfile(path):
            raise FileNotFoundError(path)

        size = os.path.getsize(path)
        digest = sha256_file(path)

        # Keep protocol overhead safely below optical capacity.
        data_capacity = max(
            1,
            self.codec.capacity_bytes - 96
        )

        total = max(
            1,
            (size + data_capacity - 1) // data_capacity
        )

        metadata = (
            f"name={os.path.basename(path)}\n"
            f"size={size}\n"
            f"sha256={digest}\n"
        ).encode()

        window = "OptiTransfer - Sender"
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)

        # Sender camera is REQUIRED because ACK comes optically from
        # receiver screen -> sender camera.
        self.camera.open()

        try:
            print("=" * 65)
            print("STRICT STOP-AND-WAIT SENDER")
            print("=" * 65)
            print(f"File       : {path}")
            print(f"Size       : {size:,} bytes")
            print(f"Packets    : {total}")
            print(f"SHA-256    : {digest}")
            print()
            print("IMPORTANT: next DATA packet is blocked until matching ACK.")
            print("=" * 65)

            # START also follows stop-and-wait.
            # Receiver must ACK START sequence 0.
            start = pack_frame(
                FrameType.START,
                0,
                total,
                metadata
            )

            if not self.endpoint.send_and_wait_for_ack(
                window, start, 0
            ):
                raise RuntimeError(
                    "START was not acknowledged after maximum retries."
                )

            started = time.monotonic()
            sent = 0

            with open(path, "rb") as file:
                while True:
                    chunk = file.read(data_capacity)

                    if not chunk:
                        break

                    frame = pack_frame(
                        FrameType.DATA,
                        sent,
                        total,
                        chunk
                    )

                    # THIS IS THE IMPORTANT PART:
                    #
                    # This function does not return until ACK(sent)
                    # is received. Therefore the while loop cannot read
                    # or transmit packet sent+1 before ACK(sent).
                    ok = self.endpoint.send_and_wait_for_ack(
                        window,
                        frame,
                        sent
                    )

                    if not ok:
                        raise RuntimeError(
                            f"DATA #{sent} failed after "
                            f"{self.cfg.max_retries} retries."
                        )

                    sent += 1

                    elapsed = max(
                        time.monotonic() - started,
                        0.001
                    )
                    approx_speed = (
                        sent * data_capacity / elapsed / 1024
                    )

                    print(
                        f"Progress: {sent}/{total} "
                        f"({sent * 100 / total:.2f}%) | "
                        f"~{approx_speed:.2f} KB/s"
                    )

            # END must also be acknowledged.
            end = pack_frame(
                FrameType.END,
                total,
                total,
                b""
            )

            if not self.endpoint.send_and_wait_for_ack(
                window, end, total
            ):
                raise RuntimeError(
                    "END was not acknowledged."
                )

            elapsed = max(
                time.monotonic() - started,
                0.001
            )

            print()
            print("=" * 65)
            print("TRANSFER COMPLETED")
            print("=" * 65)
            print(f"Packets sent : {sent}")
            print(f"Retries      : {self.endpoint.retry_count}")
            print(f"Elapsed      : {elapsed:.2f} s")
            print(f"SHA-256      : {digest}")
            print("=" * 65)

            cv2.waitKey(0)

        finally:
            self.camera.close()
            cv2.destroyAllWindows()
