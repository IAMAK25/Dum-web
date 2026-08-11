import cv2

class Camera:
    def __init__(self, cfg):
        self.cfg = cfg
        self.cap = None

    def open(self):
        self.cap = cv2.VideoCapture(self.cfg.camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.camera_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.camera_height)

        if not self.cap.isOpened():
            raise RuntimeError(
                "Camera could not be opened. Check OS permissions "
                "and camera_index."
            )

    def read(self):
        if self.cap is None:
            raise RuntimeError("Camera is not open.")

        ok, frame = self.cap.read()

        if not ok or frame is None:
            raise RuntimeError("Camera frame capture failed.")

        return frame

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
