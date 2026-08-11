import os
import cv2

from .camera import Camera
from .integrity import sha256_file
from .optical import OpticalCodec
from .protocol import FrameType, pack_frame, unpack_frame

class Receiver:
    def __init__(self, cfg):
        self.cfg = cfg
        self.codec = OpticalCodec(cfg)
        self.camera = Camera(cfg)

        self.last_accepted_data = -1
        self.start_received = False
        self.total = None
        self.metadata = {}
        self.packets = {}

    def display_control(self, window, frame):
        image = self.codec.encode(frame)
        cv2.imshow(window, image)
        cv2.waitKey(1)

    def send_ack(self, window, sequence):
        ack = pack_frame(
            FrameType.ACK,
            sequence,
            self.total or 0,
            b""
        )
        print(f"TX ACK #{sequence}")
        self.display_control(window, ack)
        # Keep ACK visible long enough for sender camera to capture it.
        # This is ACK only; it does not cause the receiver to accept
        # another DATA packet.
        import time
        time.sleep(self.cfg.frame_hold_s)

    def send_nack(self, window, sequence):
        nack = pack_frame(
            FrameType.NACK,
            sequence,
            self.total or 0,
            b""
        )
        print(f"TX NACK #{sequence}")
        self.display_control(window, nack)
        import time
        time.sleep(self.cfg.frame_hold_s)

    def decode_from_camera(self):
        frame = self.camera.read()

        corners = self.codec.locate_board(frame)

        if corners is None:
            return frame, None

        board = self.codec.rectify(frame, corners)
        raw = self.codec.decode(board)
        parsed = unpack_frame(raw) if raw else None

        return frame, parsed

    def run(self, output_dir="received_files"):
        os.makedirs(output_dir, exist_ok=True)

        self.camera.open()

        camera_window = "OptiTransfer - Receiver Camera"
        ack_window = "OptiTransfer - Receiver ACK"

        cv2.namedWindow(
            camera_window,
            cv2.WINDOW_NORMAL
        )
        cv2.namedWindow(
            ack_window,
            cv2.WINDOW_NORMAL
        )

        print("=" * 65)
        print("STRICT STOP-AND-WAIT RECEIVER")
        print("=" * 65)
        print("Receiver waits for one packet, validates it, ACKs it,")
        print("and only then waits for the next packet.")
        print("=" * 65)

        try:
            while True:
                frame, parsed = self.decode_from_camera()

                preview = frame.copy()

                if parsed:
                    kind = parsed["type"]
                    sequence = parsed["sequence"]

                    cv2.putText(
                        preview,
                        f"{kind.name} #{sequence}",
                        (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2
                    )

                    if kind == FrameType.START:
                        try:
                            text = parsed["payload"].decode("utf-8")
                            self.metadata = {}

                            for line in text.splitlines():
                                if "=" in line:
                                    key, value = line.split("=", 1)
                                    self.metadata[key] = value

                            self.total = parsed["total"]
                            self.start_received = True
                            self.packets.clear()
                            self.last_accepted_data = -1

                            print(
                                f"START received: "
                                f"{self.metadata.get('name', 'unknown')}"
                            )

                            # START itself is acknowledged before we
                            # return to waiting for DATA #0.
                            self.send_ack(
                                ack_window,
                                sequence
                            )

                        except UnicodeDecodeError:
                            self.send_nack(
                                ack_window,
                                sequence
                            )

                    elif kind == FrameType.DATA:
                        if not self.start_received:
                            self.send_nack(
                                ack_window,
                                sequence
                            )
                        elif sequence == self.last_accepted_data + 1:
                            # Accept EXACTLY the next expected sequence.
                            self.packets[sequence] = parsed["payload"]
                            self.last_accepted_data = sequence

                            print(
                                f"DATA #{sequence} accepted "
                                f"({len(parsed['payload'])} bytes)"
                            )

                            # CRITICAL:
                            # ACK is displayed BEFORE receiver returns
                            # to camera wait. Sender cannot progress
                            # until this ACK is seen.
                            self.send_ack(
                                ack_window,
                                sequence
                            )

                        elif sequence == self.last_accepted_data:
                            # Duplicate caused by sender retrying because
                            # its ACK was lost. Never append twice.
                            print(
                                f"Duplicate DATA #{sequence}; "
                                f"re-sending ACK."
                            )
                            self.send_ack(
                                ack_window,
                                sequence
                            )

                        else:
                            # Out-of-order packet. Strict stop-and-wait
                            # should normally never produce this.
                            print(
                                f"Unexpected DATA #{sequence}; "
                                f"expected #{self.last_accepted_data + 1}"
                            )
                            self.send_nack(
                                ack_window,
                                sequence
                            )

                    elif kind == FrameType.END:
                        expected_total = parsed["total"]

                        if (
                            self.start_received
                            and len(self.packets) == expected_total
                            and self.last_accepted_data == expected_total - 1
                        ):
                            print("END received; validating file.")

                            output = self._write_and_verify(
                                output_dir
                            )

                            # END is acknowledged only after file
                            # reconstruction and SHA-256 verification.
                            self.total = expected_total
                            self.send_ack(
                                ack_window,
                                sequence
                            )

                            print(
                                f"TRANSFER SUCCESSFUL: {output}"
                            )
                            break

                        print(
                            "END received but packets are incomplete."
                        )
                        self.send_nack(
                            ack_window,
                            sequence
                        )

                cv2.imshow(
                    camera_window,
                    preview
                )

                key = cv2.waitKey(
                    self.cfg.camera_poll_delay_ms
                ) & 0xff

                if key in (27, ord("q")):
                    print("Receiver cancelled.")
                    return

        finally:
            self.camera.close()
            cv2.destroyAllWindows()

    def _write_and_verify(self, output_dir):
        filename = os.path.basename(
            self.metadata.get(
                "name",
                "received_file.bin"
            )
        )

        output = os.path.join(
            output_dir,
            filename
        )

        base, ext = os.path.splitext(output)
        counter = 1

        while os.path.exists(output):
            output = f"{base}_{counter}{ext}"
            counter += 1

        with open(output, "wb") as file:
            for index in range(self.total):
                if index not in self.packets:
                    raise RuntimeError(
                        f"Missing packet #{index}"
                    )
                file.write(self.packets[index])

        actual = sha256_file(output)
        expected = self.metadata.get("sha256")

        if expected and actual != expected:
            raise RuntimeError(
                "SHA-256 mismatch. "
                f"Expected={expected}, Actual={actual}"
            )

        print(f"SHA-256 verified: {actual}")
        return output
