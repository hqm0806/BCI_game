"""图片区域框选工具 - 打开图片，鼠标拖拽框选矩形区域，终端输出四点坐标"""

import sys

from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow


class ImageLabel(QLabel):
    """支持绘制选择框的图片标签"""

    def __init__(self, selector):
        super().__init__()
        self.selector = selector
        self.setMouseTracking(True)

    def paintEvent(self, event):
        super().paintEvent(event)
        s = self.selector
        if s.drawing or s.start_point != s.end_point:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(255, 0, 0), 2, Qt.SolidLine))
            painter.setBrush(QColor(255, 0, 0, 40))
            rect = QRect(s.start_point, s.end_point).normalized()
            painter.drawRect(rect)
        for rect in s.saved_rects:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(0, 255, 0), 2, Qt.DashLine))
            painter.setBrush(QColor(0, 255, 0, 30))
            painter.drawRect(rect)


class RegionSelector(QMainWindow):
    """图片区域框选窗口"""

    def __init__(self, image_path):
        super().__init__()
        self.setWindowTitle(f"区域框选 - {image_path}")
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.drawing = False
        self.saved_rects = []

        self.label = ImageLabel(self)
        self.setCentralWidget(self.label)

        self.pixmap = QPixmap(image_path)
        if self.pixmap.isNull():
            print(f"无法加载图片: {image_path}")
            sys.exit(1)

        self.label.setPixmap(self.pixmap)
        self.label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setFixedSize(self.pixmap.width(), self.pixmap.height())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = self.label.mapFrom(self, event.pos())
            self.start_point = pos
            self.end_point = pos
            self.drawing = True

    def mouseMoveEvent(self, event):
        if self.drawing:
            self.end_point = self.label.mapFrom(self, event.pos())
            self.label.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drawing:
            self.end_point = self.label.mapFrom(self, event.pos())
            self.drawing = False
            rect = QRect(self.start_point, self.end_point).normalized()
            if rect.width() > 2 and rect.height() > 2:
                self.saved_rects.append(rect)
            self.label.update()
            self._print_coords(rect)

    def _print_coords(self, rect):
        x_min, y_min = rect.x(), rect.y()
        x_max, y_max = rect.x() + rect.width(), rect.y() + rect.height()

        print(f"第 {len(self.saved_rects)} 个选区")
        print(f"左上: ({x_min}, {y_min})")
        print(f"右上: ({x_max}, {y_min})")
        print(f"右下: ({x_max}, {y_max})")
        print(f"左下: ({x_min}, {y_max})")
        print(f"尺寸: {rect.width()} x {rect.height()}")
        print("-" * 40)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            if self.saved_rects:
                self.saved_rects.pop()
                self.label.update()
                print("已撤销上一个选区")


def main():
    if len(sys.argv) < 2:
        print("用法: python -m utils.region_selector <图片路径>")
        print("操作: 鼠标拖拽框选矩形区域，终端输出四点坐标")
        sys.exit(1)

    app = QApplication(sys.argv)
    window = RegionSelector(sys.argv[1])
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
