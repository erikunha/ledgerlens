"""Generate proposed LedgerLens public demo API contracts. DESIGN-ONLY, not implemented server.

Run: python verification/generate_contracts.py
"""
from pathlib import Path
import json
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / 'contracts' / 'schemas'
EXAMPLES = ROOT / 'contracts' / 'examples'
SCHEMAS.mkdir(parents=True, exist_ok=True)
EXAMPLES.mkdir(parents=True, exist_ok=True)
BASE = 'https://example.invalid/ledgerlens/spec/'  # illustrative $id, no external validation requests

def obj(properties, required=(), additional=False, description=None):
    d = {'type':'object','properties':properties,'required':list(required),'additionalProperties':additional}
    if description: d['description']=description
    return d

def s(pattern=None, enum=None, minLength=None):
    d={'type':'string'}
    if pattern:d['pattern']=pattern
    if enum:d['enum']=enum
    if minLength is not None:d['minLength']=minLength
    return d

def i(minimum=0, maximum=None):
    d={'type':'integer','minimum':minimum}
    if maximum is not None:d['maximum']=maximum
    return d

def schema(name,body):
    body = {'$schema':'https://json-schema.org/draft/2020-12/schema', '$id':BASE+name, '$comment':'Design contract, not deployed implementation.', **body}
    (SCHEMAS/name).write_text(json.dumps(body,indent=2,ensure_ascii=False)+'\n')
    return body

mutation_kinds = {
 'refund.apply_fx_adjustment': obj({'refund_id':s(r'^R-[0-9]{4}$'),'applied_rate':s(r'^[0-9]+(?:\.[0-9]{1,8})?$'),'effective_at':{'type':'string','format':'date-time'}},('refund_id','applied_rate','effective_at')),
 'payment.simulate_duplicate':obj({'transaction_id':s(r'^TX-[0-9]{4}$'),'elapsed_seconds':i(1,300)},('transaction_id','elapsed_seconds')),
 'chargeback.change_deadline':obj({'chargeback_id':s(r'^CB-[0-9]{4}$'),'new_deadline':{'type':'string','format':'date'}},('chargeback_id','new_deadline')),
 'tool.fx_outage':obj({'enabled':{'type':'boolean'},'error_code':s(enum=['UPSTREAM_UNAVAILABLE'])},('enabled','error_code')),
 'record.inject_untrusted_note':obj({'record_id':s(minLength=1),'text':{'type':'string','minLength':1,'maxLength':300}},('record_id','text'))
}
mutation_variants=[]
for kind,data in mutation_kinds.items():
    mutation_variants.append(obj({'kind':{'const':kind},'data':data,'reason':{'type':'string','maxLength':200}},('kind','data')))
mut = schema('scenario-mutation.schema.json',{
    'title':'ScenarioMutationRequest','description':'Constrained, ephemeral sandbox actions. All events apply only to visitor-owned simulated ledgers.',
    'oneOf': mutation_variants
})

trace_event = schema('trace-event.schema.json',{
 'title':'TraceEvent','type':'object','additionalProperties':False,
 'required':['schema_version','run_id','seq','at','event_type','payload'],
 'properties':{
    'schema_version':{'const':'1'},'run_id':s(minLength=1),'seq':i(1),
    'at':{'type':'string','format':'date-time'},
    'event_type':s(enum=['run.started','plan.created','span.started','span.ended','evidence.added','claim.verdict','run.status','run.completed','run.failed','run.cancelled','heartbeat']),
    'span_id':{'type':['string','null']},'parent_span_id':{'type':['string','null']},
    'payload':{'type':'object'},'snapshot_sha256':s(r'^[a-f0-9]{64}$'),
    'mode':s(enum=['recorded_replay','deterministic_sandbox','live_agent'])
 }})

model_profile = schema('model-profile.schema.json',{
 'title':'ModelProfile','type':'object','additionalProperties':False,
 'required':['profile_id','provider','model_id','display_name','capabilities','status','enabled_in_public_demo','pricing'],
 'properties':{
    'profile_id':s(minLength=1),'provider':s(enum=['openai','anthropic','google','local']),
    'model_id':s(minLength=1),'display_name':s(minLength=1),
    'capabilities':{'type':'array','uniqueItems':True,'items':s(enum=['chat','tool_calling','structured_output','reasoning'])},
    'status':s(enum=['tested','experimental','disabled','retired']),
    'enabled_in_public_demo':{'type':'boolean'},
    'pricing':obj({'source':s(enum=['provider','manual','unknown']),'last_verified':{'type':['string','null']},'input_per_1m_usd':{'type':['number','null'],'minimum':0},'output_per_1m_usd':{'type':['number','null'],'minimum':0}},('source','last_verified','input_per_1m_usd','output_per_1m_usd')),
 }})

limits=obj({'max_model_calls':i(1,20),'max_tool_calls':i(1,40),'max_wall_seconds':i(5,180),'max_output_tokens':i(128,16000)},('max_model_calls','max_tool_calls','max_wall_seconds','max_output_tokens'))

run_request=schema('live-run-request.schema.json',{
 'title':'RunRequest','type':'object','additionalProperties':False,
 'required':['mode','scenario_id','sandbox_id','expected_revision','account_id','question','variant','limits'],
 'properties':{
    'mode':s(enum=['live_agent','deterministic_sandbox']),
    'scenario_id':s(r'^S[0-9]{2}$'),'sandbox_id':s(minLength=1),
    'expected_revision':i(0), 'account_id':s(r'^(?:C-[0-9]{4}|M-[0-9]{2})$'),
    'question':{'type':'string','minLength':1,'maxLength':2000},
    'variant':s(enum=['A','B','C','D']),
    'model_profile_id':s(minLength=1),'credential_handle':s(minLength=1),'limits':limits,
 },
 'allOf':[{'if':{'properties':{'mode':{'const':'live_agent'}}},'then':{'required':['model_profile_id','credential_handle']}}]
})

amount=obj({'amount':s(r'^-?[0-9]+(?:\.[0-9]+)?$'),'currency':s(r'^[A-Z]{3}$')},('amount','currency'))
evidence=obj({'id':s(minLength=1),'source_type':s(enum=['sql','ledger_api','policy','fx','calc','case']),'tool':s(minLength=1),'ref':s(minLength=1),'content':s(),'retrieved_at':{'type':'string','format':'date-time'}},('id','source_type','tool','ref','content','retrieved_at'))
claim=obj({'id':s(minLength=1),'text':s(minLength=1),'kind':s(enum=['fact','numeric','policy','inference']),'evidence_ids':{'type':'array','items':s(minLength=1)}},('id','text','kind','evidence_ids'))
verdict=obj({'claim_id':s(minLength=1),'label':s(enum=['supported','contradicted','not_enough_evidence']),'method':s(enum=['nli','numeric','rule','none']),'evidence_ids':{'type':'array','items':s(minLength=1)},'note':{'type':['string','null']}},('claim_id','label','method','evidence_ids'))
public_result=schema('public-investigation-result.schema.json',{
 'title':'PublicInvestigationResult','type':'object','additionalProperties':False,
 'required':['schema_version','run_id','mode','snapshot_sha256','answer','claims','evidence','verdicts','verification_status','requires_human_review','recommended_action'],
 'properties':{
    'schema_version':{'const':'1'},'run_id':s(minLength=1),'mode':s(enum=['recorded_replay','deterministic_sandbox','live_agent']),
    'snapshot_sha256':s(r'^[a-f0-9]{64}$'),'account_id':s(minLength=1),
    'answer':s(), 'claims':{'type':'array','items':claim},'evidence':{'type':'array','items':evidence},'verdicts':{'type':'array','items':verdict},
    'verification_status':s(enum=['complete','partial','unavailable','timed_out']),
    'requires_human_review':{'type':'boolean'},
    'recommended_action':s(enum=['none','explain_to_customer','issue_refund','reject_refund','submit_chargeback_evidence','escalate_to_human','ask_for_clarification']),
    'missing_information':{'type':'array','items':s()},'metadata':{'type':'object'}
 }})

replay_bundle = schema('replay-bundle.schema.json',{
 'title':'RecordedReplayBundle','type':'object','additionalProperties':False,
 'required':['schema_version','replay_id','capture_kind','recorded_at','scenario_id','snapshot_sha256','code_sha','model_profile','run_result','events'],
 'properties':{
    'schema_version':{'const':'1'},'replay_id':s(minLength=1),
    'capture_kind':s(enum=['real_model_recorded','scripted_fixture']),
    'recorded_at':{'type':'string','format':'date-time'},'scenario_id':s(r'^S[0-9]{2}$'),
    'snapshot_sha256':s(r'^[a-f0-9]{64}$'),'code_sha':s(r'^[a-f0-9]{40}$'),
    'model_profile':s(minLength=1),'prompt_hash':s(), 'policy_version':s(), 'redaction_version':s(),
    'run_result':{'$ref':BASE+'public-investigation-result.schema.json'},
    'events':{'type':'array','items':{'$ref':BASE+'trace-event.schema.json'}},
 }})

# Write valid example values for schema validation, but label them design fixtures only.
blank='0'*64
example_mut={'kind':'tool.fx_outage','data':{'enabled':True,'error_code':'UPSTREAM_UNAVAILABLE'},'reason':'Demonstrate missing rate'}
example_trace={'schema_version':'1','run_id':'run_demo_001','seq':2,'at':'2026-11-11T12:00:00Z','event_type':'span.ended','span_id':'s2','parent_span_id':'s1','payload':{'name':'query_ledger','status':'ok','duration_ms':19},'snapshot_sha256':blank,'mode':'recorded_replay'}
example_model={'profile_id':'openai-verified-small','provider':'openai','model_id':'gpt-4.1-mini','display_name':'Example tool-calling model','capabilities':['chat','tool_calling','structured_output'],'status':'experimental','enabled_in_public_demo':False,'pricing':{'source':'unknown','last_verified':None,'input_per_1m_usd':None,'output_per_1m_usd':None}}
example_run={'mode':'live_agent','scenario_id':'S01','sandbox_id':'sb_demo','expected_revision':0,'account_id':'C-0412','question':'Why was the refund lower?','variant':'C','model_profile_id':'openai-verified-small','credential_handle':'cred_example','limits':{'max_model_calls':8,'max_tool_calls':12,'max_wall_seconds':60,'max_output_tokens':2500}}
example_result={'schema_version':'1','run_id':'run_demo_001','mode':'recorded_replay','snapshot_sha256':blank,'account_id':'C-0412','answer':'The FX rate caused a difference [fx:1].','claims':[{'id':'CL1','text':'The FX rate caused a difference.','kind':'fact','evidence_ids':['fx:1']}],'evidence':[{'id':'fx:1','source_type':'fx','tool':'get_reference_fx','ref':'fixture:eur-brl','content':'sample FX rate fixture','retrieved_at':'2026-11-11T12:00:00Z'}],'verdicts':[{'claim_id':'CL1','label':'not_enough_evidence','method':'nli','evidence_ids':['fx:1'],'note':'Illustrative; not a verified real claim.'}],'verification_status':'partial','requires_human_review':True,'recommended_action':'escalate_to_human','missing_information':['Original exchange rate'],'metadata':{'design_example':True}}
example_bundle={'schema_version':'1','replay_id':'replay_demo_001','capture_kind':'scripted_fixture','recorded_at':'2026-11-11T12:00:00Z','scenario_id':'S01','snapshot_sha256':blank,'code_sha':'0'*40,'model_profile':'scripted-fixture','prompt_hash':'illustrative','policy_version':'1','redaction_version':'1','run_result':example_result,'events':[example_trace]}
exs={'sandbox-fault-mutation.json':example_mut,'trace-event.json':example_trace,'model-profile.json':example_model,'live-run-request.json':example_run,'public-investigation-result.json':example_result,'replay-bundle-example.json':example_bundle}
for name,entry in exs.items():
    (EXAMPLES/name).write_text(json.dumps(entry,ensure_ascii=False,indent=2)+'\n')

# OpenAPI contract assembled from typed schema resources; these are design interfaces.
components={
 'schemas':{
    'Error':obj({'code':s(),'message':s(),'retryable':{'type':'boolean'},'request_id':s()},('code','message','retryable','request_id')),
    'Session':obj({'id':s(),'expires_at':{'type':'string','format':'date-time'},'mode_capabilities':{'type':'array','items':s()}},('id','expires_at','mode_capabilities')),
    'Scenario':obj({'id':s(),'title':s(),'description':s(),'modes':{'type':'array','items':s()}},('id','title','description','modes')),
    'Sandbox':obj({'id':s(),'base_snapshot_id':s(),'snapshot_sha256':s(),'revision':i(),'expires_at':{'type':'string','format':'date-time'}},('id','base_snapshot_id','snapshot_sha256','revision','expires_at')),
    'Mutation':{'$ref':'./schemas/scenario-mutation.schema.json'},
    'TraceEvent':{'$ref':'./schemas/trace-event.schema.json'},
    'RunRequest':{'$ref':'./schemas/live-run-request.schema.json'},
    'PublicResult':{'$ref':'./schemas/public-investigation-result.schema.json'},
    'ModelProfile':{'$ref':'./schemas/model-profile.schema.json'},
    'ReplayBundle':{'$ref':'./schemas/replay-bundle.schema.json'},
    'RunAccepted':obj({'run_id':s(),'status':s(enum=['queued','running']),'events_url':s(),'result_url':s()},('run_id','status','events_url','result_url')),
    'CredentialAccepted':obj({'credential_handle':s(),'provider':s(),'expires_at':{'type':'string','format':'date-time'},'validation_status':s()},('credential_handle','provider','expires_at','validation_status')),
 },
 'responses':{'Error':{'description':'Normalized error','content':{'application/json':{'schema':{'$ref':'#/components/schemas/Error'}}}}},
 'securitySchemes':{'anonymousSession':{'type':'apiKey','in':'cookie','name':'ledgerlens_session','description':'Opaque signed HttpOnly demo session cookie, not user identity.'}}
}

def ref(name):return {'$ref':'#/components/schemas/'+name}
def body(name,req=True):return {'required':req,'content':{'application/json':{'schema':ref(name)}}}
def response(code,desc,name=None,ctype='application/json'):
    return {str(code):{'description':desc,**({'content':{ctype:{'schema':ref(name)}}} if name else {})}}
def op(summary,responses,params=None,request=None,session=False):
    d={'summary':summary,'responses':responses}
    if params:d['parameters']=params
    if request:d['requestBody']=request
    if session:d['security']=[{'anonymousSession':[]}]
    return d
pathparam=lambda name:{'name':name,'in':'path','required':True,'schema':s(minLength=1)}
queryparam=lambda name, required=False:{'name':name,'in':'query','required':required,'schema':s(minLength=1)}
headerparam=lambda name:{'name':name,'in':'header','required':True,'schema':s(minLength=1)}
paths={
 '/v1/public/scenarios':{'get':op('Published scenario catalog',{'200':{'description':'Scenario list','content':{'application/json':{'schema':{'type':'array','items':ref('Scenario')}}}}})},
 '/v1/public/replays/{replay_id}':{'get':op('Published sanitized replay bundle',response(200,'Replay', 'ReplayBundle'),[pathparam('replay_id')])},
 '/v1/public/evaluations':{'get':op('Published evaluation manifests',{'200':{'description':'Versioned benchmark summaries','content':{'application/json':{'schema':{'type':'array','items':{'type':'object'}}}}}})},
 '/v1/public/model-profiles':{'get':op('Verified model profiles',{'200':{'description':'Profiles','content':{'application/json':{'schema':{'type':'array','items':ref('ModelProfile')}}}}})},
 '/v1/sessions':{'post':op('Start anonymous demo session',response(201,'Session issued','Session'))},
 '/v1/sessions/current':{'delete':op('End session and purge keys/branches',response(204,'Session ended'),session=True)},
 '/v1/sandboxes':{'post':op('Create isolated sandbox',response(201,'Sandbox created','Sandbox'),request={'required':True,'content':{'application/json':{'schema':obj({'scenario_id':s(r'^S[0-9]{2}$')},('scenario_id',))}}},session=True)},
 '/v1/sandboxes/{sandbox_id}':{'get':op('Read owned sandbox state',response(200,'Sandbox','Sandbox'),[pathparam('sandbox_id')],session=True)},
 '/v1/sandboxes/{sandbox_id}/ledger':{'get':op('Read account-scoped simulation ledger',{'200':{'description':'Bounded ledger lines','content':{'application/json':{'schema':obj({'items':{'type':'array','items':{'type':'object'}},'next_cursor':{'type':['string','null']}},('items','next_cursor'))}}}},[pathparam('sandbox_id'),queryparam('account_id', True),queryparam('cursor')],session=True)},
 '/v1/sandboxes/{sandbox_id}/mutations/preview':{'post':op('Validate and preview mutation without writing',{'200':{'description':'Preview with impacted rows/invariants','content':{'application/json':{'schema':{'type':'object'}}}}},[pathparam('sandbox_id')],body('Mutation'),True)},
 '/v1/sandboxes/{sandbox_id}/mutations':{'post':op('Append typed sandbox mutation atomically',{'200':{'description':'Applied command with new revision and hash','content':{'application/json':{'schema':{'type':'object'}}}}},[pathparam('sandbox_id'),headerparam('Idempotency-Key'),headerparam('If-Match')],body('Mutation'),True)},
 '/v1/sandboxes/{sandbox_id}/reset':{'post':op('Reset sandbox to immutable snapshot',response(200,'Reset branch','Sandbox'),[pathparam('sandbox_id')],session=True)},
 '/v1/sessions/current/provider-credentials':{'post':op('Register ephemeral BYOK key without persistence',response(201,'Ephemeral handle','CredentialAccepted'),request={'required':True,'content':{'application/json':{'schema':obj({'provider':s(enum=['openai','anthropic','google']),'api_key':s(minLength=10)},('provider','api_key'))}}},session=True)},
 '/v1/sessions/current/provider-credentials/{handle}':{'delete':op('Revoke ephemeral key',response(204,'Revoked'),[pathparam('handle')],session=True)},
 '/v1/runs':{'post':op('Queue a bounded analysis run',response(202,'Run accepted','RunAccepted'),params=[headerparam('Idempotency-Key')],request=body('RunRequest'),session=True)},
 '/v1/runs/{run_id}':{'get':op('Read owned run status and optional final result',{'200':{'description':'Run envelope','content':{'application/json':{'schema':{'type':'object'}}}}},[pathparam('run_id')],session=True)},
 '/v1/runs/{run_id}/events':{'get':op('Live SSE event stream for owned run',{'200':{'description':'SSE stream of TraceEvent JSON','content':{'text/event-stream':{'schema':{'type':'string'}}}}},[pathparam('run_id')],session=True)},
 '/v1/runs/{run_id}/cancel':{'post':op('Request cancellation of owned run',response(202,'Cancellation requested'),[pathparam('run_id')],session=True)},
 '/healthz':{'get':op('Low-information health/readiness',{'200':{'description':'Ready','content':{'application/json':{'schema':obj({'status':s(enum=['ok','degraded'])},('status',))}}}})}
}
api={'openapi':'3.1.0','info':{'title':'LedgerLens Lab Demo API (proposed)','version':'0.1.0','description':'Public educational demo endpoints, design-only; no live financial actions. Provider keys ephemeral.'},'servers':[{'url':'http://localhost:8000','description':'Local proposed service'}],'paths':paths,'components':components}
(ROOT/'contracts'/'openapi.yaml').write_text(yaml.safe_dump(api,sort_keys=False,allow_unicode=True,width=110))
print('Wrote',len(list(SCHEMAS.glob('*.json'))),'JSON Schemas,',len(exs),'examples,',len(paths),'OpenAPI paths')
