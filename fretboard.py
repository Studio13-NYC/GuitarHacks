"""Resizable feedback for inferred positions in Find Everywhere."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import QWidget, QSizePolicy
from exercises import STRINGS


class Fretboard(QWidget):
    def __init__(self):
        super().__init__()
        self.found = []
        self.mistakes = []
        self.setMinimumHeight(180)
        self.setMaximumHeight(320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self.setStyleSheet('background:transparent;')
        self.setAccessibleName('Fretboard: no positions credited')

    def set_found(self, cards, mistakes=()):
        self.found = list(cards)
        self.mistakes = list(mistakes)
        positions=[f'{STRINGS[c.string][1]} string, fret {c.midi-STRINGS[c.string][0]}' for c in cards]
        errors=[f'{STRINGS[string][1]} string, fret {fret}' for string,fret in mistakes]
        self.setAccessibleName('Estimated credited positions: '+('; '.join(positions) if positions else 'none')+
                               '. Estimated mistakes: '+('; '.join(errors) if errors else 'none'))
        self.update()

    def paintEvent(self, event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        left,top=60.0,34.0
        step=(self.width()-left-16)/15
        spacing=(self.height()-top-20)/5
        font=QFont('Segoe UI')
        font.setPixelSize(14)
        painter.setFont(font)
        for fret in range(15):
            x=left+(fret+.5)*step
            painter.setPen(QColor('#a7b8b1'))
            painter.drawText(QRectF(x-step/2,0,step,25),Qt.AlignmentFlag.AlignCenter,str(fret))
            if fret:
                painter.setPen(QPen(QColor('#c0ccc5' if fret==1 else '#60756b'),3 if fret==1 else 1))
                painter.drawLine(QPointF(left+fret*step,top),QPointF(left+fret*step,top+5*spacing))
        for string in range(1,7):
            y=top+(string-1)*spacing
            painter.setPen(QColor('#a7b8b1'))
            painter.drawText(QRectF(0,y-12,52,24),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignRight,STRINGS[string][1])
            painter.setPen(QPen(QColor('#60716e'),.7+string*.2))
            painter.drawLine(QPointF(left,y),QPointF(left+15*step,y))
        radius=min(10,step*.32,spacing*.35)
        for string,fret in self.mistakes:
            center=QPointF(left+(fret+.5)*step,top+(string-1)*spacing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#ff606b'))
            painter.drawEllipse(center,radius,radius)
        for index,card in enumerate(self.found):
            fret=card.midi-STRINGS[card.string][0]
            center=QPointF(left+(fret+.5)*step,top+(card.string-1)*spacing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#b6e4cc'))
            painter.drawEllipse(center,radius,radius)
            if index==len(self.found)-1:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor('#edf3ef'),2))
                painter.drawEllipse(center,radius+4,radius+4)
