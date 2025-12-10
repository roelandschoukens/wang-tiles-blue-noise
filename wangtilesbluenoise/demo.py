import math as _m
import time
import sys

import numpy as _np
from PySide6.QtWidgets import QApplication, QWidget, QGestureEvent, QPinchGesture, QPanGesture
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QWheelEvent, QMouseEvent, QFontMetrics
from PySide6.QtCore import Qt, QMargins, QPoint, QEvent

from . import load_tiles, load_tiles_file, RecursiveTilePoints
from . import bbox as _bbox

PX_PER_DOT = 30
DOT_SIZE = 5
UNIT_SIZE_PX = 500

if len(sys.argv) < 2:
    tileset = load_tiles()
else:
    tileset = load_tiles_file(sys.argv[1])
print(f"Tile count: {len(tileset.tiles)}")
print(f"Subdivision: {tileset.numSubtiles}")
print(f"Tile 0 base point count: {len(tileset.tiles[0].points)}")

class CanvasWidget(QWidget):

    points_blocks : list[RecursiveTilePoints] = []
    point_time : float = 0
    view_zoom = 1.0
    unit_to_px = 1.0
    box_pos = _np.array([0, 0])
    view_offset = _np.array([0, 0])
    previous_move_offset = None
    is_gesture = False
    """ Flag to track if a pinch gesture is in progress.
    
    At least on Windows, somewhere halfway a pinch gesture we also start
    receiving a mouse press and then mouse move events for every move.
    This seems to correspond to one of the two points in a pinch gesture
    and that of course throws the centering off. event.accept() makes
    no difference to avoid this. So to work around, this flag is true
    until we (hopefully) receive an event telling our gesture is ended
    or canceled, and then we can reject the mouse move events."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grabGesture(Qt.PinchGesture)
        self.grabGesture(Qt.PanGesture)

    def resizeEvent(self, event):
        self.calculate_points()
        return super().resizeEvent(event)


    def calculate_points(self):
        t0 = time.perf_counter()

        self.unit_to_px = self.view_zoom * UNIT_SIZE_PX
        screen_size = _np.array(self.size().toTuple())
        box_offset = self.view_offset / self.unit_to_px
        box_size = screen_size / self.unit_to_px
        self.box_pos = -box_offset - .5 * box_size + 0.5

        box = _np.concatenate([self.box_pos, self.box_pos + box_size])
        self.max_rank = self.unit_to_px ** 2 / PX_PER_DOT
        self.points_blocks = list(tileset.point_iter(box, self.max_rank))

        t1 = time.perf_counter()
        self.point_time = t1 - t0
        

    def do_drag(self, delta : QPoint):
        if self.view_zoom < 1:
            self.view_offset = _np.array((0, 0))
        else:
            self.view_offset = self.view_offset + delta.toTuple()


    def do_zoom(self, pos : QPoint, ratio: float):
        mouse_pos = _np.array(pos.toTuple()) - 0.5 * _np.array(self.size().toTuple())
        zoom_pos = (mouse_pos - self.view_offset) / self.view_zoom

        # Determine zoom direction and ratio from wheel delta
        self.view_zoom *= ratio
        self.view_zoom = max(0.1, min(self.view_zoom, 1.0e6))
        if self.view_zoom < 1:
            self.view_offset = _np.array((0, 0))
        else:
            self.view_offset = mouse_pos - zoom_pos * self.view_zoom


    def refresh_points(self):
        self.calculate_points()
        self.update()


    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.previous_move_offset = event.position()

    def mouseMoveEvent(self, event : QMouseEvent):
        if self.previous_move_offset is not None and not self.is_gesture:
            self.do_drag(event.position() - self.previous_move_offset)
            self.refresh_points()
            self.previous_move_offset = event.position()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.previous_move_offset = None

    def wheelEvent(self, event : QWheelEvent):
        self.do_zoom(event.position(), _m.exp2(event.angleDelta().y() * .001))
        self.refresh_points()

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Gesture:
            return self.gestureEvent(event)
        return super().event(event)

    def gestureEvent(self, event: QGestureEvent) -> bool:
        event.accept()
        if gesture := event.gesture(Qt.PinchGesture):
            if gesture.state() == Qt.GestureState.GestureCanceled or \
                    gesture.state() == Qt.GestureState.GestureFinished:
                self.is_gesture = False
            else:
                self.is_gesture = True
                pinch_gesture : QPinchGesture = gesture
                pinch_offset = self.mapFromGlobal(pinch_gesture.centerPoint())
                gmask = QPinchGesture.ScaleFactorChanged | QPinchGesture.CenterPointChanged
                if gesture.changeFlags() & gmask:
                    self.do_zoom(pinch_offset, pinch_gesture.scaleFactor())
                    self.do_drag(pinch_gesture.centerPoint() - pinch_gesture.lastCenterPoint())
                    self.refresh_points()

            return True

        return super().event(event)


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing) # For smoother drawing

        boxes = False
        color_levels = False

        # Set the pen for drawing points (e.g., color, width)
        dot_brush = QBrush(Qt.blue) # Example color: a shade of red
        box_pen = QPen(QColor(255, 0, 30, 60))
        box_pen.setWidthF(.3)

        t0 = time.perf_counter()

        tile_colors = [
            QColor(0, 20, 255),
            QColor(0, 170, 30),
            QColor(250, 40, 60),
            QColor(190, 150, 0)]

        if boxes:
            # draw tile outlines            
            painter.setBrush(Qt.NoBrush)
            for rpb in self.points_blocks[::-1]:
                tilebox = _bbox.toXYWH(rpb.bbox)
                tilebox[0:2] -= self.box_pos
                tilebox *= self.unit_to_px
                box_pen.setColor(tile_colors[rpb.level % 4])
                painter.setPen(box_pen)
                painter.drawRect(*tilebox)

        # Draw each stored point
        painter.setPen(Qt.NoPen)
        num_points = 0
        num_tiles = 0
        for rpb in self.points_blocks:
            num_points += rpb.points.shape[0]
            num_tiles += 1
            point_bl = (rpb.points - self.box_pos) * self.unit_to_px - 0.5 * DOT_SIZE
            t_bl = _np.clip(1 - 3 * (1 - rpb.ranks / self.max_rank), 0, 1)
            r_bl = _np.array(_np.floor(_np.sqrt(t_bl) * 255), dtype=int)
            if color_levels:
                dot_brush.setColor(tile_colors[rpb.level % 4])
            painter.setBrush(dot_brush)
            for point, r in zip(point_bl, r_bl):
                painter.drawEllipse(*point, DOT_SIZE, DOT_SIZE)

        t1 = time.perf_counter()
        text_lines = [
            f"{self.view_zoom:.1f}x zoom, {num_points} points from {num_tiles} tiles",
            f"calculation time: {self.point_time:.4f}s ({0.002 * num_points / self.point_time:.1f} per ms)",
            f"drawing time: {t1-t0:.4f}s"
        ]

        y = 0
        black_pen = QPen(Qt.black, 1)
        white_pen = QPen(Qt.white, 1)
        for text in text_lines:
            fm = QFontMetrics(painter.font())
            text_rect = fm.boundingRect(text).marginsAdded(QMargins(3, 1, 3, 1))
            text_pos = QPoint(0, y) - text_rect.topLeft()
            text_rect.moveTopLeft(QPoint(0, y))
            painter.fillRect(text_rect, QColor(255, 255, 255, 180))

            painter.setPen(white_pen)
            for offset in [QPoint(1, 1), QPoint(-1, 1), QPoint(1, -1), QPoint(-1, -1)]:
                painter.drawText(text_pos + offset, text)
            painter.setPen(black_pen)
            painter.drawText(text_pos, text)
            y += fm.lineSpacing()

        painter.end()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Canvas Drawing")
        self.setGeometry(100, 100, 600, 600)

        self.canvas = CanvasWidget(self)

    def resizeEvent(self, event):
        self.canvas.setGeometry(0, 0, self.width(), self.height())


app = QApplication([])
window = MainWindow()
window.show()
app.exec()

