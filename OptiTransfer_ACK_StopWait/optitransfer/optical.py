import cv2
import numpy as np

class OpticalCodec:
    def __init__(self, cfg):
        self.cfg = cfg
        self.capacity_bytes = (cfg.cols * cfg.rows) // 8

    def encode(self, payload):
        if len(payload) > self.capacity_bytes:
            raise ValueError(
                f"Optical payload too large: {len(payload)} > "
                f"{self.capacity_bytes} bytes"
            )

        padded = bytes(payload).ljust(self.capacity_bytes, b"\0")
        bits = np.unpackbits(
            np.frombuffer(padded, dtype=np.uint8)
        )

        s = self.cfg.board_size
        board = np.full((s, s), 255, dtype=np.uint8)

        border = max(5, s // 90)
        board[:border, :] = 0
        board[-border:, :] = 0
        board[:, :border] = 0
        board[:, -border:] = 0

        fs = s // 8
        margin = s // 35

        finder_positions = [
            (margin, margin),
            (s - margin - fs, margin),
            (margin, s - margin - fs),
            (s - margin - fs, s - margin - fs),
        ]

        for x, y in finder_positions:
            board[y:y + fs, x:x + fs] = 0
            inner = fs // 2
            off = (fs - inner) // 2
            board[
                y + off:y + off + inner,
                x + off:x + off + inner
            ] = 255

        left = fs + 2 * margin
        top = fs + 2 * margin
        right = s - fs - 2 * margin
        bottom = s - fs - 2 * margin

        cell_w = (right - left) / self.cfg.cols
        cell_h = (bottom - top) / self.cfg.rows

        for index, bit in enumerate(bits):
            row, col = divmod(index, self.cfg.cols)
            x0 = int(left + col * cell_w)
            x1 = int(left + (col + 1) * cell_w)
            y0 = int(top + row * cell_h)
            y1 = int(top + (row + 1) * cell_h)
            board[y0:y1, x0:x1] = 255 if bit else 0

        return board

    @staticmethod
    def order_corners(points):
        rect = np.zeros((4, 2), dtype=np.float32)
        sums = points.sum(axis=1)
        diffs = np.diff(points, axis=1).reshape(-1)

        rect[0] = points[np.argmin(sums)]
        rect[2] = points[np.argmax(sums)]
        rect[1] = points[np.argmin(diffs)]
        rect[3] = points[np.argmax(diffs)]

        return rect

    def locate_board(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        _, threshold = cv2.threshold(
            blur, 0, 255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        contours, _ = cv2.findContours(
            threshold,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        h, w = gray.shape
        image_area = h * w
        candidates = []

        for contour in contours:
            area = cv2.contourArea(contour)

            if area < image_area * self.cfg.min_board_fraction:
                continue
            if area > image_area * self.cfg.max_board_fraction:
                continue

            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(
                contour, 0.03 * perimeter, True
            )

            if len(approx) != 4:
                continue

            x, y, cw, ch = cv2.boundingRect(approx)

            if cw < 0.25 * w or ch < 0.25 * h:
                continue

            ratio = cw / max(ch, 1)

            if 0.55 <= ratio <= 1.8:
                candidates.append(
                    (area, approx.reshape(4, 2).astype(np.float32))
                )

        if not candidates:
            return None

        return self.order_corners(
            max(candidates, key=lambda item: item[0])[1]
        )

    def rectify(self, frame, corners):
        s = self.cfg.board_size

        destination = np.array(
            [
                [0, 0],
                [s - 1, 0],
                [s - 1, s - 1],
                [0, s - 1],
            ],
            dtype=np.float32,
        )

        matrix = cv2.getPerspectiveTransform(
            corners.astype(np.float32),
            destination
        )

        return cv2.warpPerspective(
            frame, matrix, (s, s)
        )

    def decode(self, board):
        gray = (
            cv2.cvtColor(board, cv2.COLOR_BGR2GRAY)
            if board.ndim == 3 else board
        )

        s = self.cfg.board_size
        fs = s // 8
        margin = s // 35

        left = fs + 2 * margin
        top = fs + 2 * margin
        right = s - fs - 2 * margin
        bottom = s - fs - 2 * margin

        cell_w = (right - left) / self.cfg.cols
        cell_h = (bottom - top) / self.cfg.rows

        bits = []

        for row in range(self.cfg.rows):
            for col in range(self.cfg.cols):
                cx = int(left + (col + 0.5) * cell_w)
                cy = int(top + (row + 0.5) * cell_h)

                radius = max(
                    1,
                    int(min(cell_w, cell_h) * 0.18)
                )

                roi = gray[
                    cy - radius:cy + radius + 1,
                    cx - radius:cx + radius + 1
                ]

                if roi.size == 0:
                    return None

                bits.append(
                    1 if float(np.mean(roi)) >= 128 else 0
                )

        return np.packbits(
            np.asarray(bits, dtype=np.uint8)
        ).tobytes()
