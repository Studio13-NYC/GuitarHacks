"""Asynchronous GPT review of practice summaries; credentials never enter the web view."""
import json
import os
from pathlib import Path
import sys

from PySide6.QtCore import QObject, Signal, QUrl, QTimer
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

TYPE_IDS = ('major','minor','dim','7','maj7','m7','m7b5','dim7','mMaj7','sus2','sus4','aug','6','m6','5')
CONTRACT = json.loads((Path(__file__).resolve().parent/'api'/'coach-contract.json').read_text(encoding='utf-8'))
SCHEMA = CONTRACT['schema']


def credentials():
    """Read only the explicitly configured env file or this project's ignored env file."""
    root = Path(sys.executable).resolve().parents[2] if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
    path = Path(os.environ.get('GUITARHACKS_OPENAI_ENV',str(root/'.env.local')))
    config = {}
    if path.is_file():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            name,sep,value=line.strip().removeprefix('export ').partition('=')
            if sep and name.strip() in ('OPENAI_API_KEY','GUITARHACKS_COACH_MODEL'):
                config[name.strip()]=value.strip().strip('\"\'')
    key=os.environ.get('OPENAI_API_KEY') or config.get('OPENAI_API_KEY','')
    model=os.environ.get('GUITARHACKS_COACH_MODEL') or config.get('GUITARHACKS_COACH_MODEL','gpt-6.1-terra')
    return key,model


def request_body(raw,model):
    if len(raw)>50000:raise ValueError('Practice summary is too large.')
    value=json.loads(raw)
    if value.get('mode') not in ('guess','paint'):raise ValueError('Choose a practice game first.')
    rows=value.get('rows',[])
    if not isinstance(rows,list) or not 1<=len(rows)<=15:raise ValueError('Invalid chord summary.')
    for row in rows:
        if not isinstance(row,dict) or row.get('id') not in TYPE_IDS:raise ValueError('Invalid chord type.')
    return {
        'model':model,'store':False,'max_output_tokens':3000,
        'reasoning':{'effort':'medium' if model.startswith('gpt-6-astra') else 'high'},
        'instructions':CONTRACT['instructions'],
        'input':json.dumps(value,ensure_ascii=False),
        'text':{'format':{'type':'json_schema','name':'practice_review','strict':True,'schema':SCHEMA}},
    }


def parse_response(raw,allowed):
    if len(raw)>1000000:raise ValueError('GPT returned an oversized response.')
    response=json.loads(raw)
    if response.get('status')!='completed':raise ValueError('GPT did not finish the review. Please retry.')
    chunks=[part.get('text','') for item in response.get('output',[]) if item.get('type')=='message'
            for part in item.get('content',[]) if part.get('type')=='output_text']
    result=json.loads(''.join(chunks))
    if not isinstance(result.get('summary'),str) or len(result['summary'])>2000:raise ValueError('Invalid GPT summary.')
    priorities=result.get('priorities')
    if not isinstance(priorities,list) or len(priorities)>15:raise ValueError('Invalid GPT priorities.')
    seen=set()
    for row in priorities:
        if (not isinstance(row,dict) or row.get('id') not in allowed or row.get('id') in seen or
            type(row.get('priority')) is not int or row['priority'] not in (-1,0,1) or
            not isinstance(row.get('reason'),str) or len(row['reason'])>500):raise ValueError('Invalid GPT priority.')
        seen.add(row['id'])
    return {'summary':result['summary'],'priorities':priorities}


class PracticeCoach(QObject):
    ready=Signal(str,str)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.network=QNetworkAccessManager(self)
        self.reply=None
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.timeout)
        self.token=''

    def cancel(self):
        self.timer.stop()
        reply,self.reply=self.reply,None
        if reply:reply.abort();reply.deleteLater()

    def error(self,token,message):self.ready.emit(token,json.dumps({'error':message}))

    def timeout(self):
        token=self.token;self.cancel();self.error(token,'GPT review timed out. Try again or use the local plan.')

    def review(self,token,raw):
        self.cancel();self.token=token
        try:
            key,model=credentials()
            if not key:
                self.error(token,'GPT is not connected: GuitarHacks needs its OpenAI API configuration.');return
            body=request_body(raw,model)
        except (OSError,ValueError,TypeError):
            self.error(token,'Could not load the GPT configuration or practice summary.');return
        request=QNetworkRequest(QUrl('https://api.openai.com/v1/responses'))
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        request.setRawHeader(b'Authorization',('Bearer '+key).encode())
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader,'application/json')
        reply=self.network.post(request,json.dumps(body).encode());self.reply=reply
        allowed={row['id'] for row in json.loads(raw)['rows']}
        reply.finished.connect(lambda:self.finished(reply,token,allowed))
        self.timer.start(60000)

    def finished(self,reply,token,allowed):
        if reply is not self.reply:return
        self.reply=None;self.timer.stop()
        try:
            status=reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if status!=200:
                message={401:'OpenAI authentication failed.',403:'This OpenAI project cannot access the review model.',429:'OpenAI usage or rate limit reached.'}.get(status,'GPT review could not connect or complete.')
                self.error(token,message);return
            value=parse_response(bytes(reply.readAll()).decode('utf-8'),allowed)
            self.ready.emit(token,json.dumps(value))
        except (ValueError,TypeError,KeyError):self.error(token,'GPT returned an unusable review. Your scores are unchanged.')
        finally:reply.deleteLater()
