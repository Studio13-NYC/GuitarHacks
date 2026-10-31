"""Local Windows speech commands, owned only by the active Play session."""
import logging
import threading
import time
from PySide6.QtCore import QThread, Signal


class VoiceCommands(QThread):
    command = Signal(str)
    status = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stopping = threading.Event()

    def stop(self): self.stopping.set()

    def run(self):
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        recognizer = context = grammar = events = None
        try:
            recognizer = win32com.client.Dispatch('SAPI.SpInprocRecognizer')
            category = win32com.client.Dispatch('SAPI.SpObjectTokenCategory')
            category.SetId(r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\AudioInput',False)
            token = win32com.client.Dispatch('SAPI.SpObjectToken')
            token.SetId(category.Default)
            recognizer.AudioInput = token
            context = recognizer.CreateRecoContext()
            events = win32com.client.WithEvents(context,RecognitionEvents)
            events.owner = self
            grammar = context.CreateGrammar(1)
            configure_grammar(grammar)
            self.status.emit('Voice ready · '+token.GetDescription()+' · Go / Next / Quit')
            while not self.stopping.wait(.02): pythoncom.PumpWaitingMessages()
        except Exception as exc:
            logging.exception('Painter voice commands failed')
            self.status.emit('Voice unavailable — use the buttons. '+str(exc))
        finally:
            if grammar:
                try: grammar.CmdSetRuleState('commands',0)
                except Exception: pass
            if recognizer:
                try: recognizer.State = 0
                except Exception: pass
            if events:
                try: events.close()
                except Exception: pass
            events = grammar = context = recognizer = None
            pythoncom.CoUninitialize()


class RecognitionEvents:
    owner = None
    last = 0.

    def OnRecognition(self, stream, position, kind, result):
        import win32com.client
        phrase=win32com.client.Dispatch(result).PhraseInfo
        word=phrase.GetText().strip().lower()
        now=time.monotonic()
        if self.owner and word in ('go','next','quit') and phrase.Rule.Confidence>=0 and now-self.last>1.2 and not self.owner.stopping.is_set():
            self.last=now
            logging.info('Painter voice accepted command=%s',word)
            self.owner.command.emit(word)


def configure_grammar(grammar):
    rule=grammar.Rules.Add('commands',33,1)
    for word in ('go','next','quit'):rule.InitialState.AddWordTransition(None,word)
    grammar.Rules.Commit()
    grammar.CmdSetRuleState('commands',1)
