"""The desktop practice chooser. Navigation never starts audio capture."""
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QWidget, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy)


def label(text, size, color='#edf3ef', bold=False):
    widget=QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    widget.setStyleSheet(f'background:transparent; color:{color}; font-size:{size}px; font-weight:{700 if bold else 400};')
    return widget


class SectionArt(QWidget):
    """Small vector previews of the actual exercises, with no downloaded assets."""
    def __init__(self, section, accent, parent=None):
        super().__init__(parent)
        self.section,self.accent=section,QColor(accent)
        self.setFixedHeight(90)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        width=self.width()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#132025'))
        p.drawRoundedRect(QRectF(0,0,width,90),12,12)
        if self.section=='notes':
            p.setPen(self.accent)
            font=QFont('Segoe UI');font.setPixelSize(60);font.setBold(True);p.setFont(font)
            p.drawText(QRectF(20,4,90,78),Qt.AlignmentFlag.AlignCenter,'C')
            font.setPixelSize(15);font.setBold(False);p.setFont(font)
            p.setPen(QColor('#bdccc5'))
            p.drawText(QRectF(123,12,width-133,65),Qt.AlignmentFlag.AlignVCenter|Qt.TextFlag.TextWordWrap,'Find the note.\nPlay it back.')
        elif self.section=='everywhere':
            p.setPen(QPen(QColor('#60726b'),1))
            for row in range(6):
                y=17+row*11;p.drawLine(QPointF(18,y),QPointF(width-18,y))
            step=(width-36)/7
            for column in range(8):
                x=18+column*step;p.drawLine(QPointF(x,17),QPointF(x,72))
            p.setBrush(self.accent);p.setPen(Qt.PenStyle.NoPen)
            for column,row in [(1,4),(3,2),(5,5),(6,0)]:
                p.drawEllipse(QPointF(18+(column-.5)*step,17+row*11),6,6)
        elif self.section=='stems':
            for row,color in enumerate(('#b6e4cc','#b8cee9','#edc882','#c9b5e8')):
                p.setPen(QPen(QColor(color),3))
                for column in range(36):
                    x=18+column*(width-36)/36
                    height=3+((column*7+row*11)%15)
                    y=15+row*20
                    p.drawLine(QPointF(x,y-height/2),QPointF(x,y+height/2))
        else:
            left=24;step=min(27,(width-130)/5)
            p.setPen(QPen(QColor('#7a8b83'),1.5))
            for string in range(6):
                x=left+string*step;p.drawLine(QPointF(x,10),QPointF(x,78))
            for fret in range(4):
                y=10+fret*22;p.drawLine(QPointF(left,y),QPointF(left+5*step,y))
            font=QFont('Segoe UI');font.setPixelSize(12);font.setBold(True);p.setFont(font)
            for string,row,degree in [(0,0,'1'),(1,2,'5'),(2,2,'1'),(3,1,'3'),(4,0,'5'),(5,0,'1')]:
                x=left+string*step;y=21+row*22
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#edc882') if degree=='1' else self.accent)
                p.drawEllipse(QPointF(x,y),10,10)
                p.setPen(QColor('#13251c'));p.drawText(QRectF(x-10,y-10,20,20),Qt.AlignmentFlag.AlignCenter,degree)
            font.setPixelSize(36);p.setFont(font);p.setPen(self.accent)
            p.drawText(QRectF(left+5*step+20,0,70,90),Qt.AlignmentFlag.AlignCenter,'C')
        p.end()


class SectionCard(QPushButton):
    def __init__(self, section, number, title, description, detail, action, accent):
        super().__init__()
        self.setObjectName('sectionCard')
        self.setAccessibleName(action)
        self.setAccessibleDescription(description+' '+detail)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f'''
            QPushButton#sectionCard {{background:#1c2a2f; border:1px solid #42574e; border-radius:18px; padding:0; text-align:left;}}
            QPushButton#sectionCard:hover {{background:#24372f; border-color:{accent};}}
            QPushButton#sectionCard:focus {{border:3px solid {accent}; background:#24372f;}}
            QPushButton#sectionCard:pressed {{background:#30483d;}}
        ''')
        box=QVBoxLayout(self);box.setContentsMargins(22,20,22,20);box.setSpacing(12)
        box.addWidget(label(number,11,accent,True))
        box.addWidget(SectionArt(section,accent,self))
        self.title_label=label(title,27,bold=True)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        box.addWidget(self.title_label)
        description_label=label(description,15,'#c0cdc6')
        description_label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        box.addWidget(description_label)
        box.addStretch(1)
        box.addWidget(label(detail,12,'#a7b8b1'))
        box.addWidget(label(action+'  →',16,accent,True))
        for child in self.findChildren(QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


class HomePage(QScrollArea):
    notes=Signal()
    everywhere=Signal()
    painter=Signal()
    connection=Signal()
    jam=Signal()
    stems=Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName('practiceHome')
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet('QScrollArea#practiceHome {border:0; background:#141b20;}')
        content=QWidget();self.setWidget(content)
        self.box=QVBoxLayout(content);self.box.setContentsMargins(34,28,34,24);self.box.setSpacing(26)
        header=QHBoxLayout()
        brand=label('GUITARHACKS  /  YOUR PRACTICE ROOM',12,'#b6e4cc',True)
        header.addWidget(brand,1)
        tagline=label('A little practice. Every day.',12,'#a7b8b1')
        tagline.setWordWrap(False)
        header.addWidget(tagline)
        self.box.addLayout(header)
        self.hero=label('Choose your practice.',58,bold=True)
        self.box.addWidget(self.hero)
        self.box.addWidget(label('Explore the fretboard, record an idea, or prepare a track to practice with.',17,'#b7c6bf'))
        self.grid=QGridLayout();self.grid.setSpacing(18);self.box.addLayout(self.grid)
        self.cards=[]
        entries=[
            ('notes','01 / PLAY & LISTEN','Note flash cards',
             'See a note and string. Find it on your guitar, and let the app check your pitch.',
             '12 cards · adjustable timer','Open flash cards','#b6e4cc',self.notes),
            ('everywhere','02 / EXPLORE THE NECK','Fretboard Explorer',
             'Look up a note or chord and see its positions. Practice a note with Find Everywhere.',
             'Notes · intervals · fretboard positions','Open Explorer','#b8cee9',self.everywhere),
            ('painter','03 / SEE & BUILD','Chord Painter',
             'Build a chord. Learn its notes and intervals, then name it or paint it from memory.',
             'No guitar connection needed','Open Chord Painter','#edc882',self.painter),
            ('stems','04 / SEPARATE & PRACTICE','StemSlicer',
             'Split a song into vocals and instruments, including separate lead and rhythm guitars.',
             'Local processing · choose your instruments','Open StemSlicer','#c9b5e8',self.stems),
        ]
        for section,number,title,description,detail,action,accent,signal in entries:
            card=SectionCard(section,number,title,description,detail,action,accent)
            card.clicked.connect(lambda checked=False,selected=signal:selected.emit())
            self.cards.append(card)
        self.columns=0
        self.connection_panel=QWidget()
        self.connection_panel.setObjectName('homeConnection')
        self.connection_panel.setStyleSheet('QWidget#homeConnection {background:#19262b; border:1px solid #34473e; border-radius:12px;}')
        connection_box=QHBoxLayout(self.connection_panel);connection_box.setContentsMargins(18,14,18,14);connection_box.setSpacing(18)
        details=QVBoxLayout();details.setSpacing(4)
        details.addWidget(label('GUITAR INPUT',10,'#b6e4cc',True))
        self.input_label=label('Choose an input in Connection',14,'#c0cdc6')
        details.addWidget(self.input_label)
        connection_box.addLayout(details,1)
        button=QPushButton('Connection settings');button.setMinimumHeight(44)
        button.setStyleSheet('font-size:13px; padding:10px 14px;')
        button.clicked.connect(lambda:self.connection.emit());connection_box.addWidget(button)
        self.box.addWidget(self.connection_panel)
        self.jam_button=QPushButton('Record with Jam  →')
        self.jam_button.setMinimumHeight(48)
        self.jam_button.clicked.connect(lambda:self.jam.emit())
        self.box.addWidget(self.jam_button)
        self.box.addWidget(label('Progress stays on this device.   ·   F11 full screen   ·   Esc windowed',12,'#a7b8b1'))
        self.box.addStretch(1)
        self.reflow()
        QWidget.setTabOrder(self.cards[0],self.cards[1])
        QWidget.setTabOrder(self.cards[1],self.cards[2])
        QWidget.setTabOrder(self.cards[2],self.cards[3])
        QWidget.setTabOrder(self.cards[3],button)

    def reflow(self):
        columns=3 if self.viewport().width()>=940 else 1
        if columns==self.columns:return
        self.columns=columns
        for card in self.cards:self.grid.removeWidget(card)
        for i in range(3):self.grid.setColumnStretch(i,1 if i<columns else 0)
        for i,card in enumerate(self.cards):
            card.setFixedHeight(364 if columns==3 else 340)
            self.grid.addWidget(card,i//columns,i%columns)
        self.hero.setStyleSheet(f'background:transparent; color:#edf3ef; font-size:{58 if columns==3 else 44}px; font-weight:700;')

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.reflow()
