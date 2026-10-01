from app.recorder.models import RawEvent
from app.recorder.normalizer import normalize

def ev(seq, et, target, context=None):
    return RawEvent(sessionId='s',sequence=seq,pageId='page-1',frameId='frame-main',eventType=et,target=target,context=context or {})

def test_fill_aggregates_and_password_redacts():
    t={"tag":"input","type":"text","name":"employeeName","value":"PoC Employee","sensitive":False}
    p={"tag":"input","type":"password","name":"password","value":None,"sensitive":True}
    actions=normalize([ev(1,'input',dict(t,value='P')),ev(2,'input',t),ev(3,'blur',t),ev(4,'input',p),ev(5,'blur',p)])
    assert actions[0].action=='fill' and actions[0].reference=='employeeName'
    assert actions[1].valueSource=='secret' and actions[1].reference=='SECRET_PASSWORD'
    assert actions[1].value is None

def test_checkbox_change_becomes_check():
    t={"tag":"input","type":"checkbox","name":"active","checked":True}
    actions=normalize([ev(1,'click',t),ev(2,'change',t)])
    assert len(actions)==1 and actions[0].action=='check'
