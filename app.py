from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime, timezone
import os, json, urllib.request, urllib.error, psycopg
from psycopg.rows import dict_row
from diagnostics import SYSTEMS, catalog, decode, diagnose
from monitor import latest as diagnostic_latest, scan_all as diagnostic_scan_all, start_background as start_diagnostic_monitor, stop_background as stop_diagnostic_monitor

app=FastAPI(title='UNG-ORION',description='Uganda National Grid National Operations Command',version='1.2.0')
DB=os.getenv('DATABASE_URL','')
JANUS=os.getenv('JANUS_BASE_URL','https://ung-iam-production.up.railway.app').rstrip('/')
def conn(): return psycopg.connect(DB,row_factory=dict_row)
def auth(permission,authorization):
    if not authorization or not authorization.lower().startswith('bearer '): raise HTTPException(401,'JANUS bearer token required')
    req=urllib.request.Request(JANUS+'/v1/auth/introspect',data=b'',method='POST',headers={'Authorization':authorization})
    try:
        with urllib.request.urlopen(req,timeout=5) as r:data=json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (401,403): raise HTTPException(401,'JANUS token invalid or expired')
        raise HTTPException(503,'JANUS unavailable')
    except Exception: raise HTTPException(503,'JANUS unavailable')
    p=data.get('principal') or {}; perms=set(p.get('permissions') or [])
    if permission not in perms and 'ung.admin' not in perms: raise HTTPException(403,f'Missing JANUS permission: {permission}')
    return p

@app.on_event('startup')
def init():
    if DB:
        with conn() as c:
            c.execute('CREATE TABLE IF NOT EXISTS operational_events(id UUID PRIMARY KEY,title TEXT,event_type TEXT,severity TEXT,status TEXT,region TEXT,source_system TEXT,details TEXT,created_at TIMESTAMPTZ,updated_at TIMESTAMPTZ)')
            c.execute('CREATE TABLE IF NOT EXISTS command_actions(id UUID PRIMARY KEY,event_id UUID,action TEXT,assigned_to TEXT,status TEXT,priority TEXT,created_by TEXT,created_at TIMESTAMPTZ,completed_at TIMESTAMPTZ)')
    start_diagnostic_monitor()

@app.on_event('shutdown')
def shutdown(): stop_diagnostic_monitor()

class EventIn(BaseModel): title:str; event_type:str='operational'; severity:str='medium'; region:str='national'; source_system:str='UNG-ORION'; details:str=''
class ActionIn(BaseModel): action:str; assigned_to:str; priority:str='normal'
class StatusIn(BaseModel): status:str
class DiagnosticIn(BaseModel): system:str; observation:dict

@app.get('/')
def root(): return {'system':'UNG-ORION','name':'National Operations Command','status':'operational','version':'1.2.0'}
@app.get('/health')
def health(): return {'status':'ok','service':'UNG-ORION','version':'1.2.0'}
@app.get('/ready')
def ready():
    try:
        with conn() as c:c.execute('SELECT 1')
        return {'status':'ready','database':'connected','janus':JANUS}
    except Exception:return {'status':'degraded','database':'unavailable','janus':JANUS}
@app.get('/v1/system')
def system(): return {'system_id':'UNG-ORION','domain':'national-operations-command','capabilities':['common-operating-picture','operational-events','command-actions','incident-coordination','system-status','janus-auth','u-code-diagnostics','automatic-health-monitoring']}

@app.get('/v1/diagnostics/systems')
def diagnostic_systems(): return SYSTEMS
@app.get('/v1/diagnostics/catalog')
def diagnostic_catalog(): return catalog()
@app.get('/v1/diagnostics/decode/{code}')
def diagnostic_decode(code:str):
    result=decode(code)
    if not result: raise HTTPException(404,'u_code_not_found')
    return result
@app.post('/v1/diagnostics/diagnose')
def diagnostic_diagnose(b:DiagnosticIn): return diagnose(b.system,b.observation)
@app.get('/v1/diagnostics/status')
def diagnostic_status(): return diagnostic_latest()
@app.post('/v1/diagnostics/scan')
def diagnostic_scan(): return diagnostic_scan_all()

@app.get('/v1/events')
def events(authorization:str|None=Header(None)):
    auth('orion.operations.read',authorization)
    with conn() as c:return c.execute('SELECT * FROM operational_events ORDER BY created_at DESC').fetchall()
@app.post('/v1/events',status_code=201)
def create_event(b:EventIn,authorization:str|None=Header(None)):
    auth('orion.operations.write',authorization); now=datetime.now(timezone.utc)
    with conn() as c:return c.execute('INSERT INTO operational_events VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',(str(uuid4()),b.title,b.event_type,b.severity,'open',b.region,b.source_system,b.details,now,now)).fetchone()
@app.post('/v1/events/{event_id}/actions',status_code=201)
def create_action(event_id:str,b:ActionIn,authorization:str|None=Header(None)):
    p=auth('orion.command.write',authorization); now=datetime.now(timezone.utc); actor=p.get('subject') or p.get('id') or 'unknown'
    with conn() as c:
        if not c.execute('SELECT id FROM operational_events WHERE id=%s',(event_id,)).fetchone(): raise HTTPException(404,'event_not_found')
        return c.execute('INSERT INTO command_actions VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',(str(uuid4()),event_id,b.action,b.assigned_to,'assigned',b.priority,actor,now,None)).fetchone()
@app.patch('/v1/events/{event_id}/status')
def event_status(event_id:str,b:StatusIn,authorization:str|None=Header(None)):
    auth('orion.command.write',authorization); now=datetime.now(timezone.utc)
    with conn() as c:
        row=c.execute('UPDATE operational_events SET status=%s,updated_at=%s WHERE id=%s RETURNING *',(b.status,now,event_id)).fetchone()
        if not row: raise HTTPException(404,'event_not_found')
        return row
@app.patch('/v1/actions/{action_id}/status')
def action_status(action_id:str,b:StatusIn,authorization:str|None=Header(None)):
    auth('orion.command.write',authorization); done=datetime.now(timezone.utc) if b.status=='completed' else None
    with conn() as c:
        row=c.execute('UPDATE command_actions SET status=%s,completed_at=%s WHERE id=%s RETURNING *',(b.status,done,action_id)).fetchone()
        if not row: raise HTTPException(404,'action_not_found')
        return row
@app.get('/v1/common-operating-picture')
def cop(authorization:str|None=Header(None)):
    auth('orion.operations.read',authorization)
    with conn() as c:
        return {'open_events':c.execute("SELECT COUNT(*) n FROM operational_events WHERE status<>'closed'").fetchone()['n'],'critical_events':c.execute("SELECT COUNT(*) n FROM operational_events WHERE severity='critical' AND status<>'closed'").fetchone()['n'],'active_actions':c.execute("SELECT COUNT(*) n FROM command_actions WHERE status<>'completed'").fetchone()['n'],'recent_events':c.execute('SELECT * FROM operational_events ORDER BY created_at DESC LIMIT 20').fetchall()}
