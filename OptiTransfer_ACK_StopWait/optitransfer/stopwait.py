import time
import cv2

from .protocol import FrameType, unpack_frame

class StopAndWaitEndpoint:
    '''
    Common optical stop-and-wait endpoint.

    Critical behavior:
        send(DATA n)
            -> wait for ACK n
            -> only then return success

    No next packet may be sent by the caller before this method returns True.
    '''

    def __init__(self, cfg, codec, camera):
        self.cfg = cfg
        self.codec = codec
        self.camera = camera
        self.retry_count = 0

    def show_frame(self, window, raw_frame, hold=True):
        image = self.codec.encode(raw_frame)

        cv2.imshow(window, image)

        # waitKey is required to keep the OpenCV window alive.
        cv2.waitKey(1)

        if hold:
            time.sleep(self.cfg.frame_hold_s)

    def read_protocol_frame(self, deadline):
        '''
        Poll the camera until timeout and return the first valid protocol frame.

        We intentionally ignore invalid/CRC-failed frames.
        '''
        while time.monotonic() < deadline:
            frame = self.camera.read()

            corners = self.codec.locate_board(frame)
            if corners is None:
                cv2.waitKey(self.cfg.camera_poll_delay_ms)
                continue

            board = self.codec.rectify(frame, corners)
            raw = self.codec.decode(board)
            parsed = unpack_frame(raw) if raw else None

            if parsed is not None:
                return parsed

            cv2.waitKey(self.cfg.camera_poll_delay_ms)

        return None

    def wait_for_matching_control(self, sequence):
        deadline = time.monotonic() + self.cfg.ack_timeout_s

        while time.monotonic() < deadline:
            parsed = self.read_protocol_frame(deadline)

            if parsed is None:
                continue

            if parsed["sequence"] != sequence:
                continue

            if parsed["type"] in (FrameType.ACK, FrameType.NACK):
                return parsed

        return None

    def send_and_wait_for_ack(self, window, raw_frame, sequence):
        '''
        Strict ARQ.

        The same frame is displayed repeatedly only when:
          - NACK is received
          - ACK timeout occurs

        DATA sequence n is NEVER followed by n+1 until ACK n is received.
        '''
        for attempt in range(self.cfg.max_retries + 1):
            print(
                f"\nTX DATA #{sequence} "
                f"(attempt {attempt + 1}/{self.cfg.max_retries + 1})"
            )

            self.show_frame(window, raw_frame, hold=True)

            control = self.wait_for_matching_control(sequence)

            if control is None:
                print(
                    f"ACK timeout for DATA #{sequence}. "
                    "Retransmitting same packet."
                )
                if attempt < self.cfg.max_retries:
                    self.retry_count += 1
                    continue
                return False

            if control["type"] == FrameType.ACK:
                print(f"ACK #{sequence} received -> advance to next packet.")
                return True

            if control["type"] == FrameType.NACK:
                print(f"NACK #{sequence} received -> retransmit same packet.")
                if attempt < self.cfg.max_retries:
                    self.retry_count += 1
                    continue
                return False

        return False
