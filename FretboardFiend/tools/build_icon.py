"""Render the editable SVG into a multi-resolution Windows ICO, using Qt."""
from pathlib import Path
import struct
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT=Path(__file__).resolve().parents[1]


def main():
    renderer=QSvgRenderer(str(ROOT/'assets/guitarhacks.svg'))
    if not renderer.isValid():
        raise RuntimeError('Invalid application icon SVG')
    images=[]
    for size in (16,20,24,32,40,48,64,128,256):
        image=QImage(size,size,QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter=QPainter(image)
        renderer.render(painter)
        painter.end()
        buffer=QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer,'PNG'):
            raise RuntimeError('Could not encode icon')
        images.append((size,bytes(buffer.data())))
    # ICO directory entries followed by their PNG payloads (Windows Vista+).
    offset=6+16*len(images)
    directory=[]
    for size,data in images:
        directory.append(struct.pack('<BBBBHHII',size%256,size%256,0,0,1,32,len(data),offset))
        offset+=len(data)
    path=ROOT/'assets/guitarhacks.ico'
    path.write_bytes(struct.pack('<HHH',0,1,len(images))+b''.join(directory)+b''.join(data for _,data in images))
    print(path)


if __name__=='__main__':main()
