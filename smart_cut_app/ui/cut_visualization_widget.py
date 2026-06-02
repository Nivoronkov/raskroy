from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class CutPatternWidget(QWidget):
    def __init__(
        self,
        stock_length_mm: int,
        parts_data: list[dict],
        leftover_length_mm: int,
        source_text: str,
        material_text: str,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.stock_length_mm = max(stock_length_mm, 1)
        self.parts_data = parts_data
        self.leftover_length_mm = max(leftover_length_mm, 0)
        self.source_text = source_text
        self.material_text = material_text

        self.setMinimumHeight(110)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()
        margin_left = 12
        margin_right = 12
        top_text_h = 24
        bar_top = top_text_h + 8
        bar_height = 44
        bottom_text_y = bar_top + bar_height + 20

        usable_width = max(100, rect.width() - margin_left - margin_right)

        # Заголовок
        title_font = QFont()
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(
            margin_left,
            18,
            f"{self.source_text} | {self.material_text} | Хлыст: {self.stock_length_mm} мм",
        )

        # Базовая полоса
        bar_rect = QRectF(margin_left, bar_top, usable_width, bar_height)
        painter.setPen(QPen(QColor(80, 80, 80), 1))
        painter.setBrush(QColor(245, 245, 245))
        painter.drawRoundedRect(bar_rect, 4, 4)

        segment_colors = [
            QColor(255, 245, 190),
            QColor(220, 235, 255),
            QColor(220, 250, 220),
            QColor(255, 225, 225),
        ]

        x = margin_left

        for idx, part in enumerate(self.parts_data):
            length = int(part.get("length_mm", 0))
            assembly = (part.get("assembly", "") or "").strip()
            note = (part.get("note", "") or "").strip()

            seg_width = usable_width * (length / self.stock_length_mm)
            if seg_width <= 0:
                continue

            seg_rect = QRectF(x, bar_top, seg_width, bar_height)
            painter.setBrush(segment_colors[idx % len(segment_colors)])
            painter.setPen(QPen(QColor(90, 90, 90), 1))
            painter.drawRect(seg_rect)

            text = self._build_segment_text(seg_width, length, assembly, note)
            if text:
                font = QFont()
                if seg_width >= 120:
                    font.setPointSize(8)
                elif seg_width >= 80:
                    font.setPointSize(7)
                else:
                    font.setPointSize(6)

                painter.setFont(font)
                painter.drawText(
                    seg_rect.adjusted(2, 2, -2, -2),
                    Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                    text,
                )

            x += seg_width

        # Остаток
        if self.leftover_length_mm > 0:
            leftover_width = usable_width * (self.leftover_length_mm / self.stock_length_mm)
            if leftover_width > 0:
                leftover_rect = QRectF(
                    margin_left + usable_width - leftover_width,
                    bar_top,
                    leftover_width,
                    bar_height,
                )
                painter.setBrush(QColor(235, 235, 235))
                painter.setPen(QPen(QColor(120, 120, 120), 1, Qt.PenStyle.DashLine))
                painter.drawRect(leftover_rect)

                if leftover_width >= 50:
                    font = QFont()
                    font.setPointSize(7)
                    painter.setFont(font)
                    painter.drawText(
                        leftover_rect.adjusted(2, 2, -2, -2),
                        Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                        f"Ост.\n{self.leftover_length_mm}",
                    )

        # Нижняя подпись
        painter.setPen(QColor(60, 60, 60))
        painter.setFont(QFont())
        part_lengths = [str(part.get("length_mm", 0)) for part in self.parts_data]
        painter.drawText(
            margin_left,
            bottom_text_y,
            f"Детали: {' + '.join(part_lengths)}   |   Остаток: {self.leftover_length_mm} мм",
        )

    def _build_segment_text(
        self,
        seg_width: float,
        length: int,
        assembly: str,
        note: str,
    ) -> str:
        """
        Подбирает объем текста под ширину сегмента.
        """
        if seg_width < 28:
            return ""

        if seg_width < 60:
            return str(length)

        if seg_width < 110:
            if assembly:
                return f"{length}\n{assembly}"
            return str(length)

        if seg_width >= 110:
            lines = [str(length)]
            if assembly:
                lines.append(assembly)
            if note:
                lines.append(note)
            return "\n".join(lines[:3])

        return str(length)