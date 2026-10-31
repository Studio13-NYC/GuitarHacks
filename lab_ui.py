"""Native practice pages using the same visual language as Chord Painter."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QScrollArea, QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy

INK='#f4f2e9'
MINT='#b6e4cc'
MUTED='#b0bcb7'
GOLD='#edc882'


def caption(text='',size=13,color=MUTED,bold=False):
    label=QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setStyleSheet(f'background:transparent; color:{color}; font-size:{size}px; font-weight:{700 if bold else 400};')
    label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
    return label


class LabTitle(QLabel):
    def __init__(self,text):
        super().__init__(text)
        self.maximum=48
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)

    def fit(self):
        font=QFont('Segoe UI');font.setBold(True)
        for size in range(self.maximum,23,-1):
            font.setPixelSize(size)
            if max((QFontMetrics(font).horizontalAdvance(word) for word in self.text().split()),default=0)<=self.width():break
        self.setStyleSheet(f'background:transparent; color:{INK}; font-size:{size}px; font-weight:700;')

    def setText(self,text):
        super().setText(text);self.fit()

    def resizeEvent(self,event):
        super().resizeEvent(event);self.fit()


class LabPage(QScrollArea):
    """Header, intro, lower-left controls, and a generous practice canvas."""
    def __init__(self,section,title,description,home_callback):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content=QWidget();self.setWidget(content)
        self.outer=QVBoxLayout(content)
        self.outer.setContentsMargins(26,20,26,22);self.outer.setSpacing(24)
        header=QHBoxLayout();header.setSpacing(20)
        self.brand=caption('GUITARHACKS   /   '+section.upper(),11,MINT,True)
        header.addWidget(self.brand,1)
        self.home=QPushButton('← Home');self.home.setObjectName('quiet')
        self.home.clicked.connect(home_callback);header.addWidget(self.home)
        self.outer.addLayout(header)
        line=QWidget();line.setFixedHeight(1);line.setStyleSheet('background:#33423e;')
        self.outer.addWidget(line)
        self.grid=QGridLayout();self.grid.setSpacing(24);self.outer.addLayout(self.grid,1)
        self.intro=QWidget();intro=QVBoxLayout(self.intro);intro.setContentsMargins(0,0,0,0);intro.setSpacing(16)
        self.eyebrow=caption('SEE IT. FIND IT. PLAY IT.',10,GOLD,True);intro.addWidget(self.eyebrow)
        self.title=LabTitle(title);intro.addWidget(self.title)
        self.description=caption(description,15);intro.addWidget(self.description)
        intro.addStretch()
        self.controls=QWidget();self.controls.setObjectName('labControls')
        self.controls.setStyleSheet('QWidget#labControls {background:#1c292b; border:1px solid #3c4e45; border-radius:18px;}')
        self.control_box=QVBoxLayout(self.controls);self.control_box.setContentsMargins(18,18,18,18);self.control_box.setSpacing(12)
        self.workspace=QWidget();self.workspace.setObjectName('labWorkspace')
        self.workspace.setStyleSheet('QWidget#labWorkspace {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #202f32,stop:1 #192529); border:1px solid #3b4c47; border-radius:24px;}')
        self.work=QVBoxLayout(self.workspace);self.work.setContentsMargins(24,22,24,22);self.work.setSpacing(16)
        self.foot=caption('One clean note. Mute briefly between answers. Your progress stays on this device.',12)
        self.outer.addWidget(self.foot)
        self.wide=None;self.reflow()

    def reflow(self):
        wide=self.viewport().width()>=900
        if wide==self.wide:return
        self.wide=wide
        for item in (self.intro,self.controls,self.workspace):self.grid.removeWidget(item)
        self.grid.setColumnStretch(0,0 if wide else 1);self.grid.setColumnStretch(1,1 if wide else 0)
        for i in range(3):self.grid.setRowStretch(i,0)
        self.intro.setFixedWidth(250 if wide else self.viewport().width()-52)
        self.controls.setMinimumWidth(250 if wide else 0)
        self.controls.setMaximumWidth(250 if wide else 16777215)
        self.workspace.setMinimumHeight(570 if wide else 470)
        if wide:
            self.grid.addWidget(self.intro,0,0)
            self.grid.addWidget(self.controls,1,0,Qt.AlignmentFlag.AlignBottom)
            self.grid.addWidget(self.workspace,0,1,2,1)
            self.grid.setRowStretch(0,1)
        else:
            self.grid.addWidget(self.intro,0,0)
            self.grid.addWidget(self.workspace,1,0)
            self.grid.addWidget(self.controls,2,0)
        self.title.maximum=48 if wide else 36;self.title.fit()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.reflow()
        if not self.wide:self.intro.setFixedWidth(max(0,self.viewport().width()-52))
