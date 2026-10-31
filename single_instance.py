"""One practice window per data folder, including repeated executable launches."""
import hashlib
import os
from pathlib import Path
from PySide6.QtCore import QObject, QLockFile, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance(QObject):
    activated=Signal()

    def __init__(self,data_dir,parent=None):
        super().__init__(parent)
        folder=Path(data_dir).resolve();folder.mkdir(parents=True,exist_ok=True)
        identity=os.path.normcase(str(folder))
        self.name='GuitarHacks-'+hashlib.sha256(identity.encode()).hexdigest()[:24]
        self.lock=QLockFile(str(folder/'.guitarhacks.lock'))
        self.lock.setStaleLockTime(0)
        self.server=QLocalServer(self)
        self.server.newConnection.connect(self._activate)
        self.owner=False

    def acquire(self):
        if self.lock.tryLock(0):
            self.owner=True
            QLocalServer.removeServer(self.name)
            if not self.server.listen(self.name):
                self.close()
                raise RuntimeError('Could not start the app window connection.')
            return True
        socket=QLocalSocket()
        socket.connectToServer(self.name)
        if not socket.waitForConnected(3000):
            raise RuntimeError('GuitarHacks is already starting or closing. Please try opening it again in a moment.')
        socket.disconnectFromServer()
        return False

    def _activate(self):
        while self.server.hasPendingConnections():
            socket=self.server.nextPendingConnection()
            socket.close();socket.deleteLater()
            self.activated.emit()

    def close(self):
        if self.owner:
            self.server.close();self.lock.unlock();self.owner=False
