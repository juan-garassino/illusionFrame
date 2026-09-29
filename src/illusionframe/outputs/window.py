"""OpenCV windows: the live loop view and the mask setup tool. All calls stay on the main thread."""

from __future__ import annotations

import cv2
import numpy as np

from illusionframe.outputs.wall_preview import project

KEYS = {ord("q"): "q", 27: "q", ord(" "): " ", ord("n"): "n", ord("s"): "s", ord("v"): "v"}


class LiveWindow:  # pragma: no cover - needs a display
    """Shows the loop; trackbars for strength and feedback; `v` toggles the on-the-wall preview."""

    def __init__(
        self,
        painting: np.ndarray,
        title: str = "illusionFrame",
        wall: bool = False,
        strength: float = 0.5,
        feedback: float = 0.5,
    ):
        self.painting, self.title, self.wall = painting, title, wall
        cv2.namedWindow(title, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(title, painting.shape[1], painting.shape[0])
        cv2.createTrackbar("strength", title, int(strength * 100), 100, lambda _: None)
        cv2.createTrackbar("feedback", title, int(feedback * 100), 80, lambda _: None)

    def show(self, frame: np.ndarray) -> str | None:
        view = project(self.painting, frame) if self.wall else frame
        cv2.imshow(self.title, cv2.cvtColor(view, cv2.COLOR_RGB2BGR))
        key = KEYS.get(cv2.waitKey(1) & 0xFF)
        if key == "v":
            self.wall = not self.wall
        if cv2.getWindowProperty(self.title, cv2.WND_PROP_VISIBLE) < 1:
            return "q"
        return key

    def controls(self) -> dict:
        return {
            "strength": cv2.getTrackbarPos("strength", self.title) / 100,
            "feedback": cv2.getTrackbarPos("feedback", self.title) / 100,
        }

    def close(self) -> None:
        cv2.destroyWindow(self.title)
        cv2.waitKey(1)


def pick_points(canvas: np.ndarray, title: str, preview=None) -> tuple[list[list[float]], list[int]] | None:
    """Click points on the canvas (left = include, right = exclude). Enter saves, r resets, q aborts.

    `preview(points, labels) -> bool mask | None` is drawn live when given. Returns normalized points.
    """  # pragma: no cover - needs a display
    h, w = canvas.shape[:2]
    points: list[list[float]] = []
    labels: list[int] = []

    def on_mouse(event, x, y, flags, param):
        if event in (cv2.EVENT_LBUTTONDOWN, cv2.EVENT_RBUTTONDOWN):
            points.append([(x + 0.5) / w, (y + 0.5) / h])
            labels.append(1 if event == cv2.EVENT_LBUTTONDOWN else 0)

    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(title, on_mouse)
    try:
        while True:
            view = canvas.copy()
            mask = preview(points, labels) if (preview and points) else None
            if mask is not None:
                view[mask] = (0.5 * view[mask] + 0.5 * np.array([255, 60, 60])).astype(np.uint8)
            for (px, py), lab in zip(points, labels, strict=True):
                color = (60, 220, 90) if lab else (230, 40, 40)
                cv2.circle(view, (int(px * w), int(py * h)), 5, color, -1)
            cv2.imshow(title, cv2.cvtColor(view, cv2.COLOR_RGB2BGR))
            key = cv2.waitKey(30) & 0xFF
            if key in (13, 10):
                return points, labels
            if key == ord("r"):
                points.clear()
                labels.clear()
            if key in (ord("q"), 27) or cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                return None
    finally:
        cv2.destroyWindow(title)
        cv2.waitKey(1)
