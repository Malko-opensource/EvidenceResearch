/* Agent-controlled scenes; deterministic, read-only presentation of the shared store. */
import {buildViewModel, buildClientView, compareRecords, clipText, labelState, interpretMetric, displayMetricLabel} from './view_model.js';
const $ = id => document.getElementById(id);
const PAGE = 20, VISIBLE = 3, COMPARE = 6;
const state = {token:null,tools:[],workspace:'',scene:'overview',selected:'',goalSelection:'',focus:'',snapshot:null,record:null,summary:null,goal:null,
  limit:PAGE,offset:0,memory:null,overviewMemory:null,memoryArgs:{query:'',outcome:null,verification:null,limit:PAGE,offset:0},
  evidence:null,records:[],compareArgs:null,compareMissing:[],calls:[],pending:0,serial:0,latest:0,refreshing:null,
  connected:false,explanation:'',fingerprints:new Map(),booted:false,refreshScope:'',summarySignature:''};
const scenes = {overview:['의뢰한 연구의 답','현재 확인된 결과와 다음 확인을 봅니다.'],
  analysis:['결과를 읽는 방법','실제 측정값을 사전에 고정한 기준과 비교합니다.'],
  comparison:['시도 사이의 차이','평가 조건이 확인된 시도만 함께 비교합니다.'],
  memory:['이전 시도에서 배운 것','결과와 적용 조건을 함께 읽습니다.'],
  activity:['연구에 쓴 시간과 비용','실제 사건, 실행 시간과 기록된 비용 관측의 범위를 봅니다.'],
  graph:['결론과 근거의 연결','실제로 기록된 가설, 실험, 원본과 결정의 관계를 봅니다.'],
  stability:['반복 결과의 안정성','등록된 반복 설계의 실제 측정 분포와 계산 범위를 봅니다.'],
  evidence:['근거의 원문','보존된 원문과 현재 해시를 확인합니다.']};
export const presentationTools = [
 {name:'research_view',description:'Control spectator scenes without human clicks or research mutations. overview is a client brief: commissioned question, selected result against frozen criteria, confirmed scope and next evidence. clientBrief returns source references. focus or explanation replaces the brief with one explanatory scene; omit both to return to the brief. analysis compares measurements with frozen criteria; comparison groups at most six full records by evaluation conditions; graph expands recorded relationships; stability shows descriptive registered repeat distributions; memory searches lessons; activity shows actual events and scoped resource observations. On narrow graph screens the selected relationship is shown, with omitted attempts declared. All summaries return versioned references and structured judgment facts. explanation is an unverified external-agent statement.',
 inputSchema:{type:'object',additionalProperties:false,properties:{
 workspace:{type:'string',description:'Relative workspace; defaults to current display.'},
 scene:{type:'string',enum:['overview','analysis','comparison','memory','activity','graph','stability'],default:'overview'},
 goal:{type:'string',description:'Optional persistent goal to report; uses the same goal as CLI and stdio MCP.'},
 focus:{type:'string',enum:['hypothesis','experiment','evidence','verification','conclusion'],description:'Agent-selected explanation focus; does not change research state.'},
 registration:{type:'string',description:'Optional experiment to focus, including an off-page record.'},
 compare:{type:'array',maxItems:6,items:{type:'object',additionalProperties:false,required:['workspace','registration'],properties:{workspace:{type:'string'},registration:{type:'string'}}},description:'comparison, graph or stability: explicit records beneath the configured root. No scientific ranking.'},
 query:{type:'string',default:''},outcome:{type:['string','null'],enum:[null,'success','failure','inconclusive']},
 verification:{type:['string','null'],enum:[null,'pending','passed','failed','inconclusive']},
 limit:{type:'integer',minimum:1,maximum:100,default:PAGE},offset:{type:'integer',minimum:0,default:0},
 explanation:{type:'string',maxLength:2000,description:'External-agent statement; separate from verified evidence.'}}},
 annotations:{readOnlyHint:true}},
 {name:'research_inspect_evidence',description:'Open one preserved evidence file in a full-width evidence scene. Obtain IDs with research_show. Hash checked through the existing evidence API. Does not execute, verify, adopt, or mutate state. Return via research_view.',
 inputSchema:{type:'object',additionalProperties:false,required:['registration','evidence'],properties:{workspace:{type:'string'},registration:{type:'string'},evidence:{type:'string'},explanation:{type:'string',maxLength:2000}}},
 annotations:{readOnlyHint:true}}
];
function el(tag,className,text){const n=document.createElement(tag);if(className)n.className=className;if(text!==undefined&&text!==null)n.textContent=String(text);return n;}
function svg(tag,attrs={},text){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,String(v)));if(text!==undefined)n.textContent=text;return n;}
function json(value){return JSON.stringify(value,null,2);}
function finiteJson(value){return JSON.stringify(value,(_k,v)=>{if(typeof v==='number'&&!Number.isFinite(v))throw Error('Input must be finite JSON.');return v;});}
function tone(value){if(['succeeded','passed','adopted','valid','success'].includes(value))return 'good';if(['failed','rejected','tampered','missing','failure'].includes(value))return 'bad';if(['running','unknown','inconclusive'].includes(value))return 'warn';return 'quiet';}
function statePresentation(value,dimension,currentEvidenceUnconfirmed=false){const historical=currentEvidenceUnconfirmed&&((dimension==='verification'&&value==='passed')||(dimension==='decision'&&value==='adopted'));return {text:(historical?'과거 ':'')+labelState(value,dimension),tone:historical?'warn':tone(value)};}
function badge(value,prefix='',dimension,currentEvidenceUnconfirmed=false){const display=statePresentation(value,dimension,currentEvidenceUnconfirmed),node=el('span','state-badge '+display.tone,prefix+display.text);node.dataset.state=value;return node;}
function time(value,seconds=true){const d=new Date(typeof value==='number'?(seconds?value*1000:value):value);return !value||Number.isNaN(d.getTime())?'시각 미확인':new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(d);}
function dateTime(value){const d=new Date(typeof value==='number'?value*1000:value);return Number.isNaN(d.getTime())?'시각 미확인':new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(d);}
function qs(value){return new URLSearchParams(Object.entries(value).filter(([,v])=>v!==undefined&&v!==null)).toString();}
function status(){return state.snapshot?.status||{goals:[],hypotheses:[],registrations:[],revision:null,total:0};}
function envelopeError(code,message,details={}){return {ok:false,error:{code,message,details}};}
function errorText(result){return (result.error?.code||'ERROR')+' · '+(result.error?.message||'조회할 수 없습니다.');}
function notify(text=''){state.noticeKind=text.startsWith('CONNECTION_ERROR')?'connection':'operation';$('notice').textContent=text;$('notice').hidden=!text;}
function animate(node){if(matchMedia('(prefers-reduced-motion: reduce)').matches||typeof node.animate!=='function')return;node.getAnimations().forEach(a=>a.cancel());node.animate([{opacity:.6,transform:'translateY(5px)'},{opacity:1,transform:'translateY(0)'}],{duration:260,easing:'ease-out'});}
function replaceChanged(node,key,children,transition=true){if(state.fingerprints.get(node.id)===key)return;state.fingerprints.set(node.id,key);node.replaceChildren(...children);if(transition)animate(node);}
function connection(online){state.connected=online;$('connection-status').textContent=online?'연구 상태 연결':'연결 확인 필요';$('connection-status').dataset.state=online?'connected':'disconnected';}
async function request(path,options={}){try{const res=await fetch(path,{cache:'no-store',credentials:'same-origin',...options}),value=await res.json();if(!value||typeof value.ok!=='boolean')throw Error('Invalid response envelope.');connection(true);return value;}catch(error){connection(false);state.token=null;return envelopeError('CONNECTION_ERROR',error.message);}}
async function ensureSession(){const value=await request('/api/bootstrap');if(value.ok){state.token=value.data.session_token;$('app-version').textContent=value.data.version;}return value;}
async function core(name,args){return request('/api/call',{method:'POST',headers:{'Content-Type':'application/json','X-Research-Session':state.token},body:finiteJson({tool:name,arguments:args})});}
function relativeWorkspace(value){return typeof value==='string'&&value.length>0&&!/^[\\/]|^[A-Za-z]:/.test(value)&&!value.split(/[\\/]/).some(p=>p==='..');}
function workspace(name){if(name===state.workspace)return;state.workspace=name;state.selected='';state.goalSelection='';state.focus='';state.snapshot=null;state.record=null;state.summary=null;state.goal=null;state.evidence=null;state.memory=null;state.overviewMemory=null;state.records=[];state.compareArgs=null;state.compareMissing=[];state.offset=0;state.summarySignature='';state.fingerprints.clear();$('workspace-name').textContent=name||'에이전트 연결 대기';try{localStorage.setItem('research-state-workspace',name);}catch(_){}}
function setScene(scene){state.scene=scene;document.body.dataset.scene=scene;document.body.dataset.presentation=scene==='overview'?(state.focus||state.explanation?'explanation':'brief'):'detail';$('scene-title').textContent=scenes[scene][0];$('scene-caption').textContent=scenes[scene][1];}
function model(){const memory=state.scene==='overview'?state.overviewMemory:state.memory,vm=buildViewModel({snapshot:state.snapshot,record:state.record,goal:state.goal,summary:state.summary,memory,records:['comparison','graph','stability'].includes(state.scene)?state.records:[],limit:state.limit,offset:state.offset,workspace:state.workspace});if(state.scene==='overview'&&memory)vm.refs=vm.refs.filter(ref=>ref.field!=='memory').concat(memory.queries.map(query=>({field:'memory',...query.arguments,revision:query.revision,goal_version:vm.report.goalVersion})));return vm;}
export function getViewState(){return {workspace:state.workspace,scene:state.scene,goal:state.snapshot?.report?.goal?.id||state.goalSelection||null,goalVersion:state.snapshot?.report?.goal?.version??null,focus:state.focus||null,selectedRegistration:state.selected,revision:status().revision,limit:state.limit,offset:state.offset,pendingCalls:state.pending,connected:state.connected,humanControls:false,memory:{...state.memoryArgs},overviewMemory:state.overviewMemory?{selection:state.overviewMemory.selection,queries:state.overviewMemory.queries}:null,evidence:state.evidence?.evidence?.id||null,visibleLimit:VISIBLE,comparison:state.records.map(r=>({workspace:r.workspace||state.workspace,registration:r.registration.id})),sourceReferences:model().refs};}
function card(kicker,title,classes=''){const n=el('section','card '+classes),head=el('header','card-heading');head.append(el('span','card-kicker',kicker),el('h2','card-title',title));n.append(head);return n;}
function note(text){return el('p','card-note',text);}
function conditions(items,limit=8){const n=el('dl','condition-list');items.slice(0,limit).forEach(item=>{const row=el('div');row.append(el('dt','',item.label),el('dd','',typeof item.value==='string'?item.value:json(item.value)));n.append(row);});if(items.length>limit)n.append(note('표시 '+limit+' / '+items.length+'개 조건 · 원본은 에이전트가 조회합니다.'));return n;}
function metricPlot(metric,compact=false,spec=state.record?.registration?.spec||{}){
 const box=el('div','metric-row'),head=el('div','metric-heading');
 const label=displayMetricLabel(metric.name,spec);
 head.append(el('strong','',label),el('span','metric-unit',metric.unit));box.append(head);
 const resultTone=!metric.supported?'quiet':metric.criteria.some(c=>c.passed===false)?'bad':'good';
 box.append(el('div','metric-number '+(!metric.supported?'muted':resultTone),metric.value===null?'미측정':compactNumber(metric.value)));
 const numeric=metric.criteria.filter(c=>typeof c.threshold==='number'&&Number.isFinite(c.threshold));
 if(metric.value===null&&!numeric.length){box.append(note('측정값과 등록 기준이 아직 없습니다.'));return box;}
 const domain=metric.domain||[0,1],min=domain[0],max=domain[1],scale=Math.max(Math.abs(min),Math.abs(max),1),range=max/scale-min/scale||1,x=v=>42+Math.max(0,Math.min(1,(v/scale-min/scale)/range))*476;
 const drawing=svg('svg',{viewBox:'0 0 560 96',role:'img','aria-label':label+' '+(metric.value===null?'측정값 없음':metric.supported?'실측 '+metric.value:'과거 수치 '+metric.value+' · 현재 확인 안 됨')+' · 기준 '+metric.criteria.map(c=>c.op+' '+c.threshold).join(', ')+' · '+metric.unit});
 numeric.forEach(c=>{if(['>=','>','<=','<'].includes(c.op)){const a=['>=','>'].includes(c.op)?x(c.threshold):42,b=['>=','>'].includes(c.op)?518:x(c.threshold);drawing.append(svg('rect',{x:a,y:26,width:Math.max(0,b-a),height:18,class:'plot-region'}));}});
 drawing.append(svg('line',{x1:42,x2:518,y1:36,y2:36,class:'plot-axis'}));
 [min,min/2+max/2,max].forEach(v=>drawing.append(svg('line',{x1:x(v),x2:x(v),y1:47,y2:53,class:'plot-tick'}),svg('text',{x:x(v),y:73,'text-anchor':'middle',class:'plot-label'},Number(v.toPrecision(4)))));
 numeric.forEach(c=>drawing.append(svg('line',{x1:x(c.threshold),x2:x(c.threshold),y1:17,y2:53,class:'plot-threshold'})));
 if(metric.value!==null)drawing.append(svg('circle',{cx:x(metric.value),cy:36,r:7,class:'plot-measure '+(metric.supported?'':'historical'),'data-tone':resultTone}));
 box.append(drawing);const legend=el('div','metric-legend');
 legend.append(el('span',metric.supported?'measure-key':'historical-key',metric.value===null?'측정값 없음':metric.supported?'● 독립 측정':'○ 과거 수치 · 현재 확인 안 됨'),el('span','threshold-key','│ 사전등록 기준'));
 box.append(legend);
 if(!compact)metric.criteria.forEach(c=>box.append(note('기준 '+c.op+' '+c.threshold+' · '+(c.passed===true?'충족':c.passed===false?'미충족':'현재 판정 미확인'))));
 if(compact&&metric.value!==null&&numeric.length===1){const c=numeric[0],delta=metric.value-c.threshold;box.append(note('사전등록 '+c.op+' '+compactNumber(c.threshold)+' · '+(delta===0?'기준과 일치':'기준보다 '+compactNumber(Math.abs(delta))+' '+(delta<0?'낮음':'높음'))));}
 else box.append(note((metric.interpretation||interpretMetric(metric)).text));
 if(!metric.criteria.length)box.append(note('등록 기준 없음 · 숫자만으로 성공을 판단하지 않습니다.'));
 return box;
}
function distribution(vm){const box=el('div','distribution'),parts=[['실행',vm.distribution.execution],['검증 기록',vm.distribution.verification],['결정',vm.distribution.decision]];parts.forEach(([label,items])=>{const row=el('div','distribution-row'),track=el('div','distribution-track'),legend=el('div','distribution-legend');row.append(el('strong','',label));const nonzero=items.filter(i=>i.count);if(!nonzero.length)legend.append(el('span','','기록 없음'));nonzero.forEach(item=>{legend.append(el('span','',item.label+' '+item.count));const s=el('span','distribution-segment '+tone(item.key));s.style.flexGrow=item.count;s.setAttribute('aria-label',item.label+' '+item.count+'건');track.append(s);});row.append(legend,track);box.append(row);});box.append(note(vm.scope.label));return box;}
function timelinePlot(timeline){const items=timeline.items.filter(i=>Number.isFinite(i.created));if(!items.length)return note('시각이 기록된 사건이 없습니다.');const min=Math.min(...items.map(i=>i.created)),max=Math.max(...items.map(i=>i.created)),range=max-min||1,drawing=svg('svg',{viewBox:'0 0 720 146',role:'img','aria-label':'실제 사건 시간축 '+dateTime(min)+'부터 '+dateTime(max)+'까지, '+items.length+'개 사건'});drawing.append(svg('line',{x1:36,x2:684,y1:66,y2:66,class:'plot-axis'}));items.forEach((item,i)=>{const x=36+(item.created-min)/range*648,y=i%2===0?38:92;drawing.append(svg('line',{x1:x,x2:x,y1:66,y2:y,class:'plot-tick'}),svg('circle',{cx:x,cy:66,r:4,class:'plot-measure'}),svg('text',{x:x,y:y+(i%2===0?-5:15),'text-anchor':'middle',class:'plot-label'},i+1));});drawing.append(svg('text',{x:36,y:138,class:'plot-label'},time(min)),svg('text',{x:684,y:138,'text-anchor':'end',class:'plot-label'},time(max)));const box=el('div','timeline-chart');box.append(drawing,note(timeline.label+' · 점 사이 간격은 실제 시간, 번호는 아래 사건 순서'));return box;}
function duration(seconds){if(typeof seconds!=='number'||!Number.isFinite(seconds))return '미확인';if(seconds<60)return new Intl.NumberFormat('ko-KR',{maximumFractionDigits:1}).format(seconds)+'초';if(seconds<3600)return Math.floor(seconds/60)+'분 '+Math.floor(seconds%60)+'초';if(seconds<86400)return Math.floor(seconds/3600)+'시간 '+Math.floor(seconds%3600/60)+'분';return Math.floor(seconds/86400)+'일 '+Math.floor(seconds%86400/3600)+'시간';}
function compactNumber(value){if(typeof value!=='number'||!Number.isFinite(value))return '미확인';if(value!==0&&(Math.abs(value)<1e-4||Math.abs(value)>=1e9))return value.toExponential(5).replace(/(\.\d*?[1-9])0+e/u,'$1e').replace(/\.0+e/u,'e');return new Intl.NumberFormat('ko-KR',{maximumFractionDigits:5}).format(value);}

function question(vm) {
  const phase=el('div','question-phase');
  phase.append(badge(vm.report.state,'','goal'));
  if(vm.report.lifecycleReported)phase.append(el('span','lifecycle-provenance','외부 연구 상태 보고'));
  const client=state.scene==='overview'?buildClientView(vm,{goal:state.snapshot?.report?.goal||state.goal}):null;
  const title=!state.snapshot?'연구 기록을 불러오고 있습니다.':client?.question.title||vm.question.title;
  const nodes=[el('span','card-kicker',client?'의뢰한 연구':'함께 살펴보는 연구'),attachRefs(el('h2','question-title',title),client?.question.refs||vm.question.refs),...(!client?[phase]:[])];
  replaceChanged($('research-context'),json({title,state:vm.report.state,reported:vm.report.lifecycleReported,client:!!client}),nodes,false);
  replaceChanged($('scene-index'),state.scene,[el('span','scene-current','에이전트가 펼친 장면')],false);
  $('revision-label').textContent='기록 '+(status().revision??'미확인');
}
const kindNames={hypothesis:'가설',experiment:'실험',evidence:'증거',verification:'검증',conclusion:'결정'};
function attachRefs(node,refs=[]) { node.dataset.sourceReferences=JSON.stringify(refs); return node; }
function recordStates(vm) {
  const strip=el('div','record-states');
  [['실행',vm.states.execution,'execution'],['검증',vm.states.verification,'verification'],['결정',vm.states.decision,'decision']].forEach(([name,value,dimension])=>{
    const row=el('div','record-state');row.append(el('span','',name),badge(value,'',dimension,!vm.trust.supported));strip.append(row);
  });return strip;
}
function focusPane(vm) {
  const view=vm.observatory,focus=state.focus&&view?.focus[state.focus],pane=el('aside','focus-pane'+(focus?'':' result-focus'));
  pane.setAttribute('aria-label',focus?'현재 초점 설명':'선택한 시도의 결과');
  if(focus) {
    pane.append(el('span','card-kicker','현재 초점 · '+kindNames[state.focus]),el('h2','focus-title',focus.title));
    const meaning=el('p','focus-meaning',focus.text);attachRefs(meaning,focus.refs);pane.append(meaning,badge(focus.state,'',state.focus==='experiment'?'execution':state.focus==='conclusion'?'decision':state.focus,focus.tone==='warn'));
    const facts=el('ul','focus-facts');(focus.lines||[]).slice(0,4).forEach(line=>facts.append(el('li','',typeof line==='string'?line:line.text)));pane.append(facts);
    if(state.focus==='verification'&&vm.primaryMetric)pane.append(metricPlot(vm.primaryMetric,true));
  } else {
    pane.append(el('span','card-kicker','선택한 시도'),el('h2','focus-title',view?.metric?'무엇을 확인했는가':'결과를 기다립니다'));
    pane.append(recordStates(vm));
    if(view?.metric){const metric=vm.metrics.find(m=>m.name===view.metric.name);if(metric)pane.append(metricPlot({...metric,label:view.metric.label},true));}
    else pane.append(el('p','focus-meaning','등록된 실측과 검증 근거가 아직 없습니다.'));
    if(view?.bottleneck){const issue=el('p','focus-issue '+view.bottleneck.tone,view.bottleneck.text);attachRefs(issue,view.bottleneck.refs);pane.append(issue);}
    const uncertainties=(view?.uncertainty||[]).slice(0,2);
    if(uncertainties.length){const box=el('div','uncertainty');box.append(el('h3','','남은 불확실성'));uncertainties.forEach(item=>box.append(attachRefs(el('p','',item.text),item.refs)));pane.append(box);}
  }
  if(state.explanation){const external=el('div','external-explanation');external.append(el('span','card-kicker','에이전트 설명 · 미검증'),el('p','',state.explanation));pane.append(external);}
  return pane;
}
function relationshipCanvas(vm,detailed=false) {
  const view=vm.observatory,graph=view?.graph,panel=el('section','research-canvas');
  const narrow=matchMedia('(max-width:700px)').matches;
  panel.setAttribute('aria-label',detailed?'조회한 실제 연구 관계':'선택한 연구의 관계와 현재 경로');
  const head=el('header','canvas-heading');
  head.append(el('h2','',detailed?'근거가 결론에 닿는 경로':'연구의 흐름'),el('span','canvas-scope',narrow&&graph?.nodes.length?'선택 1 / '+graph.total+'개 시도':(graph?.shown??0)+' / '+(graph?.total??0)+'개 시도 · 조회 범위'));
  panel.append(head);
  if(!graph?.nodes.length){const empty=el('div','canvas-empty');empty.append(el('h3','','아직 연구 경로가 없습니다'),el('p','','에이전트가 실험을 사전등록하면 실제 연결이 여기에 나타납니다.'));panel.append(empty);return panel;}
  const selectedEvidence=graph.nodes.filter(n=>n.selected&&n.kind==='evidence');
  const visibleAttempts=new Set(view.attempts.items.slice(0,detailed?COMPARE:VISIBLE).map(item=>item.registration));
  const nodes=graph.nodes.filter(n=>narrow?n.selected&&(n.kind!=='evidence'||n.id===selectedEvidence[0]?.id):detailed||n.selected||['hypothesis','experiment'].includes(n.kind)&&(n.registrations||[]).some(id=>visibleAttempts.has(id)));
  const columns=['hypothesis','experiment','evidence','verification','conclusion'],positions=new Map();
  const attempts=nodes.filter(n=>n.kind==='experiment'),rowCount=Math.max(1,attempts.length),columnCount=Math.max(...columns.map(kind=>nodes.filter(n=>n.kind===kind).length)),height=Math.max(340,rowCount*96+95,columnCount*74+95),center=height/2;
  head.lastElementChild.textContent=(narrow?'선택 ':'표시 ')+attempts.length+' / '+graph.total+'개 시도'+(narrow?'':' · 조회 '+graph.shown+'개');
  attempts.forEach((node,index)=>positions.set(node.id,{x:265,y:rowCount===1?center:65+index*(height-130)/(rowCount-1)}));
  const usedRows=new Map();
  for(const node of nodes.filter(n=>n.kind!=='experiment')) {
    const column=columns.indexOf(node.kind),linked=attempts.filter(a=>(node.registrations||[]).some(id=>(a.registrations||[]).includes(id))),ys=linked.map(a=>positions.get(a.id).y);
    let y=ys.length?ys.reduce((s,v)=>s+v,0)/ys.length:center;
    const key=column+':'+Math.round(y),count=usedRows.get(key)||0;usedRows.set(key,count+1);if(count)y+=count*68;
    positions.set(node.id,{x:90+column*175,y});
  }
  for(const kind of columns){const list=nodes.filter(node=>node.kind===kind).sort((a,b)=>positions.get(a.id).y-positions.get(b.id).y);let last=-30;list.forEach(node=>{const pos=positions.get(node.id);pos.y=Math.max(pos.y,last+68);last=pos.y;});const excess=Math.max(0,last-(height-40));if(excess)list.forEach(node=>positions.get(node.id).y-=excess);}
  if(narrow){const compactPositions={hypothesis:{x:175,y:32},experiment:{x:175,y:96},evidence:{x:82,y:174},verification:{x:268,y:174},conclusion:{x:175,y:248}};nodes.forEach(node=>positions.set(node.id,compactPositions[node.kind]));}
  const drawing=svg('svg',{viewBox:narrow?'0 0 350 280':'0 0 900 '+height,role:'img','aria-label':'원본에 기록된 가설·실험·증거·검증·결정의 연결. 표시 '+attempts.length+'개 / 전체 '+graph.total+'개 시도. '+(narrow?'선택한 시도':detailed?'조회 범위 전체':'선택한 경로 강조')});
  const defs=svg('defs'),marker=svg('marker',{id:'relation-arrow',viewBox:'0 0 10 10',refX:8,refY:5,markerWidth:5,markerHeight:5,orient:'auto-start-reverse'});marker.append(svg('path',{d:'M 1 1 L 9 5 L 1 9',fill:'none',stroke:'context-stroke','stroke-width':1.5}));defs.append(marker);drawing.append(defs);
  if(!narrow)columns.forEach((kind,index)=>drawing.append(svg('text',{x:90+index*175,y:22,'text-anchor':'middle',class:'graph-column-label'},kindNames[kind])));
  for(const edge of graph.edges) {
    const from=positions.get(edge.from),to=positions.get(edge.to);if(!from||!to)continue;
    const skip=to.x-from.x>200,x1=from.x+65,x2=to.x-65,mid=(x1+x2)/2;
    const target=nodes.find(n=>n.id===edge.to),origin=nodes.find(n=>n.id===edge.from);
    const mobilePath=origin.kind==='experiment'&&target.kind==='conclusion'?'M 240 96 C 348 96 348 248 240 248':from.y===to.y?'M '+x1+' '+from.y+' L '+x2+' '+to.y:'M '+from.x+' '+(from.y+28)+' C '+from.x+' '+(from.y+65)+' '+to.x+' '+(to.y-65)+' '+to.x+' '+(to.y-28);
    const d=narrow?mobilePath:skip?'M '+from.x+' '+(from.y+28)+' C '+from.x+' '+(from.y+80)+' '+to.x+' '+(to.y+80)+' '+to.x+' '+(to.y+28):'M '+x1+' '+from.y+' C '+mid+' '+from.y+' '+mid+' '+to.y+' '+x2+' '+to.y;
    const path=svg('path',{d,class:'research-edge'+(edge.selected?' selected':''),'marker-end':'url(#relation-arrow)'});attachRefs(path,edge.refs);drawing.append(path);
    path.append(svg('title',{},edge.label));
    if(edge.selected&&!narrow)drawing.append(svg('text',{x:skip?(from.x+to.x)/2:mid,y:skip?Math.max(from.y,to.y)+59:(from.y+to.y)/2-10,'text-anchor':'middle',class:'graph-edge-label'},edge.label));
  }
  for(const node of nodes) {
    const pos=positions.get(node.id),focused=node.selected&&state.focus===node.kind,group=svg('g',{class:'research-node'+(node.selected?' selected':'')+(focused?' focused':''),'data-key':node.kind,'data-state':node.state,'data-tone':node.tone});
    attachRefs(group,node.refs);group.append(svg('title',{},node.title+' · '+node.stateLabel+' · '+node.text));
    group.append(svg('rect',{x:pos.x-65,y:pos.y-28,width:130,height:56,rx:9,class:'node-surface'}));
    const attempt=view.attempts.items.find(a=>(node.registrations||[]).includes(a.registration));
    let title=node.kind==='experiment'?(Number.isFinite(attempt?.seed)?'Seed '+attempt.seed+' 실험':node.selected?'선택한 실험':'등록된 시도'):node.kind==='hypothesis'?'시험한 가설':node.kind==='evidence'?'실제 산출물':node.kind==='verification'?'고정 기준 검사':'외부 결정';
    if(narrow&&node.kind!=='experiment')title=kindNames[node.kind];
    group.append(svg('text',{x:pos.x,y:pos.y-3,'text-anchor':'middle',class:'graph-node-title'},clipText(title,20)),svg('text',{x:pos.x,y:pos.y+16,'text-anchor':'middle',class:'graph-node-state'},node.stateLabel));
    drawing.append(group);
  }
  const holder=el('div','canvas-drawing');holder.append(drawing);panel.append(holder);
  const legend=el('footer','canvas-legend');legend.append(el('span','','실선 · 원본에 기록된 연결'),el('span','',narrow?'다른 시도는 에이전트가 선택해 펼칩니다':'강조 · 에이전트가 선택한 경로'));if(!detailed)legend.append(el('span','','다른 시도의 근거는 관계 장면에서 펼칩니다'));else legend.append(el('span','','공유 원본은 독립 확인 횟수가 아닙니다'));panel.append(legend);
  if(narrow&&selectedEvidence.length>1)panel.append(note('산출물 연결 '+selectedEvidence.length+'개 중 1개 표시 · 에이전트가 증거 장면에서 원본을 펼칩니다.'));
  if(graph.truncated)panel.append(note('조회 범위 일부 · 에이전트가 다른 기록과 페이지를 펼칠 수 있습니다.'));
  return panel;
}
function observatoryScene(vm,detailed=false) {
  const wrap=el('div','observatory-stage');wrap.append(relationshipCanvas(vm,detailed),focusPane(vm));return wrap;
}
function clientMetricPlot(metric) {
 const figure=attachRefs(el('figure','client-metric'),metric.refs),numeric=metric.criteria.filter(c=>typeof c.threshold==='number'&&Number.isFinite(c.threshold));
 const head=el('figcaption','client-metric-heading');head.append(el('strong','',metric.label),el('span','',metric.unitKnown?metric.unit:'단위 미등록'));figure.append(head);
 if(!numeric.length||!metric.domain){figure.append(el('p','client-measurement','측정 '+compactNumber(metric.value)),note('수치 기준이 등록되지 않아 비교 그림은 생략합니다.'));return figure;}
 const [min,max]=metric.domain,scale=Math.max(Math.abs(min),Math.abs(max),1),range=max/scale-min/scale||1,x=v=>32+(v/scale-min/scale)/range*456;
 const g=svg('svg',{viewBox:'0 0 520 '+(125+Math.max(0,numeric.length-2)*16),role:'img','aria-label':metric.label+' · 현재 확인된 측정 '+metric.value+' · 등록 기준 '+numeric.map(c=>c.op+' '+c.threshold).join(', ')+' · 축 '+min+'부터 '+max+' · '+(metric.unitKnown?metric.unit:'단위 미등록')});
 g.append(svg('line',{x1:32,x2:488,y1:58,y2:58,class:'plot-axis'}));
 const negative=numeric.some(c=>c.passed===false);
 g.append(svg('circle',{cx:x(metric.value),cy:58,r:6,class:'plot-measure','data-tone':negative?'bad':'good'}),svg('text',{x:x(metric.value),y:25,'text-anchor':'middle',class:'client-value-label'},'실측 '+compactNumber(metric.value)));
 const operators={'>=':'이상','>':'초과','<=':'이하','<':'미만','==':'같음','!=':'다름'};
 numeric.forEach((c,i)=>g.append(svg('line',{x1:x(c.threshold),x2:x(c.threshold),y1:43,y2:76,class:'plot-threshold'}),svg('text',{x:x(c.threshold),y:97+i*16,'text-anchor':'middle',class:'client-criterion-label'},'기준 '+compactNumber(c.threshold)+' '+(operators[c.op]||c.op))));
 figure.append(g,note('축 '+compactNumber(min)+'–'+compactNumber(max)+' · 실측과 등록 기준의 범위'));
 return figure;
}
function clientExplanation(vm) {
 const wrap=el('section','client-explanation');
 if(state.focus)wrap.append(focusPane(vm));
 else {wrap.append(el('span','card-kicker','에이전트 설명 · 미검증'),el('h2','focus-title','에이전트가 펼친 설명'),el('p','client-external-text',state.explanation));}
 return wrap;
}
function overview(vm){
 if(!state.snapshot){const loading=el('div','client-loading');loading.append(el('h3','',state.connected?'연구 기록을 불러오고 있습니다.':'연구 기록에 연결하고 있습니다.'),note('현재 기록을 읽은 뒤 확인된 답을 보여 드립니다.'));return loading;}
 if(state.focus||state.explanation)return clientExplanation(vm);
 const brief=buildClientView(vm,{goal:state.snapshot?.report?.goal||state.goal}),wrap=attachRefs(el('article','client-brief'),brief.refs),answer=el('section','client-answer');
 answer.dataset.tone=brief.answer.tone;answer.dataset.answerStatus=brief.answer.status;
 const meaning=attachRefs(el('div','client-answer-meaning'),brief.answer.refs);meaning.append(el('p','card-kicker','선택한 시도에서 얻은 답'),el('h3','client-answer-title',brief.answer.headline));
 const metric=brief.answer.metric;
 if(!metric||metric.value===null||!metric.criteria.some(c=>typeof c.threshold==='number'))meaning.append(el('p','client-answer-detail',brief.answer.detail));
 if(brief.assurance.status==='confirmed_in_registered_scope')meaning.append(attachRefs(el('p','client-assurance-label',brief.assurance.label),brief.assurance.refs));answer.append(meaning);
 if(metric?.value!==null&&metric?.value!==undefined)answer.append(clientMetricPlot(metric));
 wrap.append(answer);
 const rows=el('dl','client-context');
 function row(label,text,refs,className=''){const item=attachRefs(el('div','client-context-row '+className),refs);item.append(el('dt','',label),el('dd','',text));rows.append(item);return item.lastElementChild;}
 row('확인 범위',brief.assurance.detail,brief.assurance.refs);
 const next=row('다음 확인',brief.followup.text,brief.followup.refs,'client-next');
 const items=[...brief.followup.requiredEvidence,...brief.limitations.items].filter((item,i,all)=>all.findIndex(other=>other.text===item.text)===i&&item.kind!==brief.followup.nextKind&&(!(metric?.value!==null&&metric?.value!==undefined)||item.kind!=='metric_unit')).slice(0,2);
 items.forEach(item=>next.append(attachRefs(el('p','client-limitation',item.text),item.refs)));
 wrap.append(rows);
 if(brief.followup.reported||vm.report.state==='active')wrap.append(attachRefs(el('p','client-progress',brief.followup.label+(brief.followup.reported&&['active','completed','paused','cancelled'].includes(vm.report.state)?' · 외부 에이전트의 진행 보고':'')),brief.followup.refs));
 return wrap;
}

function analysis(vm) {
  const wrap=el('div','analysis-grid'),result=card('등록 기준과 실제 결과','실측을 기준에 대조합니다','analysis-results');
  vm.metrics.slice(0,6).forEach(m=>result.append(metricPlot(m)));
  if(!vm.metrics.length)result.append(note('현재 확인할 수 있는 측정값이 없습니다.'));
  if(vm.metrics.length>6)result.append(note('표시 6 / '+vm.metrics.length+'개 · 에이전트가 원본을 펼칩니다.'));
  let context;
  if(state.focus)context=focusPane(vm);
  else {context=card('이 결과의 적용 범위','조건을 함께 읽습니다','analysis-context');context.append(conditions(vm.conditions,4),el('h3','','결정 이유'),el('p','',clipText(state.record?.decision?.reason||'결정 기록 대기',280)),note(vm.trust.text));}
  wrap.append(result,context);return wrap;
}
function comparison(vm){
 const wrap=el('div'),groups=compareRecords(state.records);
 wrap.append(note('비교 원본 '+state.records.length+'건 · 최대 '+COMPARE+'건 · 순위와 종합 점수를 만들지 않습니다.'));
 if(state.compareMissing.length)wrap.append(note('조회할 수 없는 비교 기록 '+state.compareMissing.length+'건 · 원본 확인 필요'));
 if(!groups.length){wrap.append(el('div','empty-scene','비교할 원본 기록이 없습니다. 에이전트가 비교할 실험을 지정하세요.'));return wrap;}
 groups.forEach((g,index)=>{
  const group=card('평가 조건 그룹 '+(index+1),g.comparable?'평가 조건이 같은 시도':'함께 순위를 매길 수 없는 기록');
  group.append(note(g.reason));
  const context=conditions((g.conditions||[]).filter(c=>['비교 기준','데이터 분할','Seed'].includes(c.label)).map(c=>({...c,value:clipText(c.value,180)})),3);
  context.setAttribute('aria-label','이 묶음의 비교 기준, 데이터 분할과 Seed 요약');
  context.querySelectorAll('dd').forEach(value=>value.classList.add('clamp-2'));
  group.append(context,note('등록 조건 요약 · 전체는 연결된 원본 등록에서 확인합니다.'));
  const sharedDomains=new Map();
  if(g.comparable)g.items.flatMap(item=>item.metrics).forEach(m=>{const d=sharedDomains.get(m.name)||m.domain;sharedDomains.set(m.name,[Math.min(d[0],m.domain[0]),Math.max(d[1],m.domain[1])]);});
  if(g.differences?.length)group.append(note('시도 차이 · '+g.differences.map(d=>typeof d==='string'?d:json(d)).join(' · ')));
  const grid=el('div','comparison-grid');
  g.items.forEach(item=>{
   const attempt=el('article','attempt-card');
   attempt.append(el('h3','clamp-2',item.title),note(typeof item.source==='string'?item.source:'소스 버전은 원본에 고정됨'));
   const statuses=el('div','badge-row'),currentEvidenceUnconfirmed=!item.metrics.length||item.metrics.some(metric=>!metric.supported);
   statuses.append(badge(item.states.execution,'','execution'),badge(item.states.verification,'','verification',currentEvidenceUnconfirmed),badge(item.states.decision,'','decision',currentEvidenceUnconfirmed));
   attempt.append(statuses);
   const spec=state.records.find(record=>record.registration.id===item.registration)?.registration.spec||{};
   item.metrics.slice(0,2).forEach(m=>attempt.append(metricPlot(sharedDomains.has(m.name)?{...m,domain:sharedDomains.get(m.name)}:m,false,spec)));
   if(!item.metrics.length)attempt.append(note('측정값 미확인'));
   grid.append(attempt);
  });
  group.append(grid);wrap.append(group);
 });
 return wrap;
}
function memory(vm){const wrap=el('div'),data=state.memory,args=state.memoryArgs;wrap.append(note('에이전트 검색 “'+(args.query||'전체')+'” · '+(args.outcome?labelState(args.outcome):'모든 결과')+' · 조회 '+(data?.items?.length||0)+' / 검색 결과 '+(data?.total||0)+'건'));const grid=el('div','memory-grid');vm.lessons.slice(0,VISIBLE).forEach(item=>{const n=card(labelState(item.outcome),'조건과 함께 읽는 교훈','attempt-card');n.append(el('h3','clamp-2',clipText(item.title,180)),el('p','clamp-3',clipText(item.summary,280)),el('p','clamp-3',clipText(item.reason||'결정 이유 기록 없음',280)),note(item.claimText),conditions(item.conditions||[],3));grid.append(n);});if(!vm.lessons.length)grid.append(el('div','empty-scene','조건에 맞는 기억이 없습니다. 빈 검색 결과는 가설의 성공·실패 증거가 아닙니다.'));wrap.append(grid,note('화면 표시 '+Math.min(VISIBLE,vm.lessons.length)+' / 이번 조회 '+vm.lessons.length+'건 · 에이전트가 limit/offset으로 다른 페이지를 펼칩니다.'));return wrap;}
function activity(vm){const wrap=el('div','analysis-grid'),events=card('실제 연구 사건','시간에 따른 상태와 근거의 도착');const visibleTimeline={...vm.timeline,items:vm.timeline.items.slice(-6),label:'시간축 표시 '+Math.min(6,vm.timeline.items.length)+'개 · '+vm.timeline.label};events.append(timelinePlot(visibleTimeline));const list=el('ol','timeline-list');vm.timeline.items.slice(-6).forEach((item,i)=>{const n=el('li','mini-event');n.append(el('time','',dateTime(item.created)),el('strong','',(i+1)+'. '+item.title));list.append(n);});events.append(list,note('목록은 최근 '+Math.min(6,vm.timeline.items.length)+'개 · 전체 시간축은 이번 조회 범위'));const calls=card('외부 에이전트 활동','이 페이지에서 요청한 내용');state.calls.slice(0,4).forEach(c=>{const n=el('div','mini-event');n.append(el('time','',time(c.created)),el('strong','',c.tool),note(c.result?(c.result.ok?'요청 완료':errorText(c.result)):'요청 처리 중'));calls.append(n);});if(!state.calls.length)calls.append(note('이 페이지의 도구 호출 없음'));calls.append(note('도구 요청 완료는 전체 연구 완료를 뜻하지 않습니다. 이 목록은 영속 연구 사건과 별개입니다.'));wrap.append(events,calls);return wrap;}
function observedTrend(items,unit,title){const values=items.filter(item=>Number.isFinite(item.created)&&Number.isFinite(item.value));if(!values.length)return note(title+' · 시각과 값이 기록된 관측 없음');const start=Math.min(...values.map(item=>item.created)),end=Math.max(...values.map(item=>item.created)),low=Math.min(0,...values.map(item=>item.value)),high=Math.max(1,...values.map(item=>item.value)),x=value=>44+(value-start)/(end-start||1)*570,y=value=>112-(value-low)/(high-low||1)*76,drawing=svg('svg',{viewBox:'0 0 660 170',role:'img','aria-label':title+' 실제 관측 '+values.length+'건 · 단위 '+unit});drawing.append(svg('line',{x1:44,x2:614,y1:112,y2:112,class:'plot-axis'}),svg('text',{x:8,y:40,class:'plot-label'},compactNumber(high)),svg('text',{x:8,y:116,class:'plot-label'},compactNumber(low)));values.forEach(item=>drawing.append(svg('circle',{cx:x(item.created),cy:y(item.value),r:5,class:'plot-measure'},'')));drawing.append(svg('text',{x:44,y:155,class:'plot-label'},time(start)),svg('text',{x:614,y:155,'text-anchor':'end',class:'plot-label'},time(end)));const box=el('div','observed-trend');box.append(note(title+' · '+unit+' · 점 사이 가로 간격은 실제 시각'),drawing);return box;}
function resourcesActivity(vm){const wrap=activity(vm),resources=card('실제 자원 관측','실행 시간·외부 비용의 관측 추이','resource-trends');resources.append(observedTrend(vm.report.trends.runs,'초','실행별 실제 소요 시간'),note('시간축 조회 '+vm.report.trends.runs.length+'건 / 선택 목표 전체 실행 '+(vm.report.trends.runsTotal??'미확인')+'건 · 전체 관측 실행 시간 '+duration(vm.report.runTime.value)+' · 시간 미확인 '+(vm.report.runTime.unknown??'미확인')+'건'));const currencies=[...new Set(vm.report.trends.costs.map(item=>item.unit))];currencies.slice(0,3).forEach(unit=>resources.append(observedTrend(vm.report.trends.costs.filter(item=>item.unit===unit),unit,'외부 보고의 개별 비용 관측')));if(!currencies.length)resources.append(note('기록된 비용 관측 없음 · 비용 0이라는 뜻이 아닙니다.'));resources.append(note('통화를 서로 합산하지 않습니다. 비용은 외부 보고이며 실제 영수증 검증을 의미하지 않습니다.'));if(vm.report.branches.length){const branches=el('div','resource-branches');vm.report.branches.slice(0,4).forEach((branch,index)=>branches.append(note('가설 분기 '+(index+1)+' · 고유 실행 '+branch.runs_total+'건 · 관측 실행 시간 '+duration(branch.wall_seconds)+' · 시간 미확인 '+branch.unknown+'건')));resources.append(branches);}wrap.append(resources);return wrap;}

function graphScene(vm){return observatoryScene(vm,true);}
function samplePlot(metric){const box=el('div','repeat-metric'),scale=metric.unit==='ratio'?100:1,unit=scale===100?'%':metric.unit,values=metric.samples.map(sample=>sample.value*scale);box.append(el('h3','',displayMetricLabel(metric.name)+' · 실측 '+metric.n+'회'));if(!metric.n){box.append(note('현재 원본과 고정 검증에 연결된 측정 없음'));return box;}let min=Math.min(...values),max=Math.max(...values);const margin=max===min?Math.max(Math.abs(min)*.1,.1):(max-min)*.15;min-=margin;max+=margin;const x=value=>40+(value-min)/(max-min)*580,drawing=svg('svg',{viewBox:'0 0 660 148',role:'img','aria-label':displayMetricLabel(metric.name)+' 실측 분포 '+metric.n+'개 · '+unit});drawing.append(svg('line',{x1:40,x2:620,y1:67,y2:67,class:'plot-axis'}));values.forEach((value,index)=>{drawing.append(svg('circle',{cx:x(value),cy:67+(index%3-1)*13,r:5,class:'plot-measure'}));});drawing.append(svg('line',{x1:x(metric.mean*scale),x2:x(metric.mean*scale),y1:36,y2:97,class:'repeat-mean'}),svg('text',{x:40,y:125,class:'plot-label'},compactNumber(min)),svg('text',{x:620,y:125,'text-anchor':'end',class:'plot-label'},compactNumber(max)));box.append(drawing,note('● 실제 반복 측정 · │ 조회 평균 · 단위 '+unit),note('평균 '+compactNumber(metric.mean*scale)+' · 범위 '+compactNumber(metric.min*scale)+'–'+compactNumber(metric.max*scale)+' · 표본 SD '+(metric.sampleSd===null?'미확인':compactNumber(metric.sampleSd*scale))),note(metric.uncertainty));return box;}
function stability(vm){const wrap=el('div','stability-scene');wrap.append(note('명시적으로 사전등록한 반복 설계만 표시 · 동일 소스·변경점·평가 조건, seed 차이는 함께 공개 · 신뢰구간이나 독립 확인 횟수로 해석하지 않습니다.'));if(!vm.stability.length){wrap.append(el('div','empty-scene','비교 가능한 반복 설계와 실제 측정이 충분히 등록되지 않았습니다. 단일 실측으로 변동이나 신뢰구간을 채우지 않습니다.'));return wrap;}vm.stability.slice(0,3).forEach(group=>{const box=card('등록된 반복 조건',group.title);box.append(note(group.scope+' · seed '+group.seeds.join(', ')));const grid=el('div','analysis-grid');group.metrics.slice(0,4).forEach(metric=>grid.append(samplePlot(metric)));box.append(grid,conditions(group.conditions.filter(item=>['비교 기준','데이터 분할','소스 버전'].includes(item.label)),3));wrap.append(box);});return wrap;}
function evidence(vm){const wrap=el('div','evidence-layout'),meta=card('원본으로 추적',state.evidence?.evidence?.name||'원본 확인 필요','evidence-meta'),data=state.evidence;if(data){meta.append(conditions([{label:'종류',value:labelState(data.evidence.kind)},{label:'파일 보존',value:'현재 해시 일치'},{label:'등록 연결',value:data.evidence.registration_id},{label:'증거 식별자',value:data.evidence.id},{label:'보존 경로',value:data.evidence.path},{label:'SHA-256',value:data.evidence.sha256},{label:'파일 크기',value:data.bytes+' bytes'}]));}else meta.append(note('원문이 없거나 현재 무결성을 확인할 수 없습니다. 에이전트가 증거를 다시 지정해야 합니다.'));meta.append(note('해시 일치는 파일 보존 상태입니다. 이 원문의 내용에 대한 과학적 타당성을 증명하지 않습니다.'),note(vm.trust.text));const original=card('보존된 내용',data?.truncated?'원문 앞부분 · 최대 256 KiB':'에이전트가 선택한 원문');const pre=el('pre','evidence-text',data?.text||'표시할 수 있는 원문 없음');pre.setAttribute('aria-label','보존된 원본 증거 내용');original.append(pre);if(data?.truncated)original.append(note('화면 표시가 잘렸습니다. 전체 보존 원본은 유지됩니다.'));wrap.append(meta,original);return wrap;}

function analysisReport(vm){return analysis(vm);}
function activityReport(vm){const wrap=resourcesActivity(vm),branches=vm.report.branches.filter(branch=>branch.resources);if(branches.length){const cost=card('가설 분기에 연결된 비용','귀속이 확인된 외부 관측의 소계','resource-trends');branches.slice(0,6).forEach((branch,index)=>{const scoped=branch.resources,items=(scoped.cost_by_currency||[]).map(item=>compactNumber(item.amount)+' '+item.currency);cost.append(note('분기 '+(index+1)+' · '+(items.length?items.join(' · '):'비용 미확인')+' · 확인된 관측 '+scoped.known_count+'건 / 미확인 관측 '+scoped.unknown_count+'건'));});cost.append(note('목표 전체에만 연결된 비용은 임의로 분기별 배분하지 않습니다. 미기록 비용은 포함되지 않습니다.'));wrap.append(cost);}return wrap;}
function render(){const vm=model();question(vm);setScene(state.scene);const draw={overview,analysis:analysisReport,comparison,memory,activity:activityReport,graph:graphScene,stability,evidence}[state.scene];const key=json({scene:state.scene,narrow:matchMedia('(max-width:700px)').matches,vm,focus:state.focus,explanation:state.explanation,evidence:state.scene==='evidence'?state.evidence:null,records:['comparison','graph','stability'].includes(state.scene)?state.records:null,calls:state.scene==='activity'?state.calls:null}),transitionKey=json({scene:state.scene,selected:state.selected,focus:state.focus,revision:status().revision,integrity:vm.trust,metrics:vm.metrics});const changed=state.fingerprints.get('scene-transition')!==transitionKey;state.fingerprints.set('scene-transition',transitionKey);const positions=!changed?[...document.querySelectorAll('#scene-content, .client-explanation, .focus-pane, #scene-content .card, .evidence-text')].map(node=>({top:node.scrollTop,left:node.scrollLeft})):null;replaceChanged($('scene-content'),key,[draw(vm)],changed);if(positions)[...document.querySelectorAll('#scene-content, .client-explanation, .focus-pane, #scene-content .card, .evidence-text')].forEach((node,i)=>{if(positions[i]){node.scrollTop=positions[i].top;node.scrollLeft=positions[i].left;}});pulseGraph();}
function drawOverview(){render();} function drawMemory(){render();} function drawEvidence(){render();} function drawFocus(){render();} function drawCalls(){if(state.scene==='activity')render();} function drawGraph(){render();}
function pulseGraph(){const call=state.calls.find(c=>!c.result),map={research_hypothesis:'hypothesis',research_register:'experiment',research_run:'experiment',research_recover:'experiment',research_verify:'verification',research_decide:'conclusion'};document.querySelectorAll('.path-node, .research-node').forEach(n=>n.classList.toggle('agent-focus',n.dataset.key===map[call?.tool]));}
function agentPhase(call,phase){document.body.dataset.phase=phase;$('agent-phase').textContent=phase==='running'?'요청 처리 중':phase==='error'?'요청 거부':phase==='succeeded'?'요청 완료':'에이전트 관전';$('agent-tool').textContent=call?.tool||'WebMCP로 장면과 초점을 변경합니다';$('agent-description').textContent=phase==='running'?'실제 응답 대기':phase==='error'?'오류 원인을 확인하세요':'사용자는 보고 싶은 내용을 에이전트에게 요청하세요';$('agent-status').textContent=phase==='running'?state.pending+'개 요청 처리 중':phase==='error'?errorText(call.result):(state.scene==='overview'&&state.focus?kindNames[state.focus]+' 설명':state.scene==='overview'&&state.explanation?'에이전트 설명':scenes[state.scene][0])+' 화면입니다.';$('action-status').hidden=phase!=='error';$('action-status').textContent=phase==='error'?errorText(call.result):'';pulseGraph();}
async function readComparison(){const name=state.workspace,selected=state.selected,explicit=state.compareArgs;const refs=explicit||[...new Set([selected,...(state.snapshot?.report?.records||[]).map(r=>r.registration.id),...status().registrations.map(r=>r.id)].filter(Boolean))].slice(0,COMPARE).map(registration=>({workspace:name,registration}));const results=await Promise.all(refs.map(async ref=>({ref,value:await core('research_show',ref)})));if(name!==state.workspace||selected!==state.selected||explicit!==state.compareArgs)return;state.records=results.filter(r=>r.value.ok).map(r=>({...r.value.data,workspace:r.ref.workspace}));state.compareMissing=results.filter(r=>!r.value.ok).map(r=>({ref:r.ref,error:r.value.error}));}
async function lookupSummary() {
  if (!state.record) return;
  const signature = json([state.workspace, state.selected, status().revision, state.record.evidence.map((item) => [item.id, item.integrity])]);
  const visible = status().registrations.find((item) => item.id === state.selected); if (visible) state.summary = visible;
  const goalId = state.record.registration.goal_id; state.goal = status().goals.find((item) => item.id === goalId) || (state.goal?.id === goalId ? state.goal : null);
  if (visible && state.goal) return;
  if (state.summary && state.summarySignature === signature) return;
  const name = state.workspace, id = state.selected;
  for (let offset = 0; ; offset += 100) {
    const response = await core('research_status', {workspace: name, goal: goalId, limit: 100, offset});
    if (state.workspace !== name || state.selected !== id || !response.ok) return;
    state.goal = response.data.goals.find((item) => item.id === goalId) || state.goal;
    const row = response.data.registrations.find((item) => item.id === id); if (row) { state.summary = row; state.summarySignature = signature; return; }
    if (offset + 100 >= response.data.total) return;
  }
}
async function readSelection() {
  if (!state.selected) return {ok: true}; const name = state.workspace, id = state.selected;
  const result = await core('research_show', {workspace: name, registration: id}); if (name !== state.workspace || id !== state.selected) return result;
  if (result.ok) { state.record = result.data; if(!state.goalSelection)state.goalSelection=result.data.registration.goal_id; await lookupSummary(); } else { state.record = null; state.summary = null; notify(errorText(result)); } return result;
}
async function readOverviewMemory(name) {
  const outcomes=['failure','success','inconclusive'];
  const replies=await Promise.all(outcomes.map(async outcome=>{const args={workspace:name,query:'',outcome,limit:1,offset:0};return {arguments:args,result:await core('research_memory',args)};}));
  if(name!==state.workspace)return;
  const successful=replies.filter(reply=>reply.result.ok),revisions=successful.map(reply=>reply.result.data.revision);
  const items=successful.flatMap(reply=>reply.result.data.items.slice(0,1));
  state.overviewMemory={items,total:successful.length===outcomes.length?successful.reduce((count,reply)=>count+reply.result.data.total,0):null,limit:VISIBLE,offset:0,
    revision:revisions.find(revision=>revision!==status().revision)??revisions[0]??null,
    selection:{method:'latest_per_outcome',outcomes,perOutcomeLimit:1,offset:0,insightPriority:outcomes,insightExcludeRegistration:state.selected,mixedRevisions:new Set(revisions).size>1},
    queries:replies.map(reply=>({arguments:reply.arguments,ok:reply.result.ok,total:reply.result.data?.total??null,revision:reply.result.data?.revision??null,
      registration:reply.result.data?.items?.[0]?.id||null,...(!reply.result.ok?{error:reply.result.error}:{} )}))};
}
export async function refresh() {
  const scope = json([state.workspace, state.limit, state.offset, state.selected,state.goalSelection]);
  if (state.refreshing) {
    if (state.refreshScope === scope) return state.refreshing;
    await state.refreshing;
    return refresh();
  }
  if (!state.workspace) { drawOverview(); return {ok: true}; }
  const name = state.workspace, limit = state.limit, offset = state.offset,goalId=state.goalSelection,selected=state.selected;
  state.refreshScope = scope;
  state.refreshing = (async () => {
    if (!state.token) { const boot = await ensureSession(); if (!boot.ok) return boot; }
    const result = await request(`/api/snapshot?${qs({workspace: name, limit, offset, registration: selected || undefined,goal:goalId||undefined})}`);
    if (name !== state.workspace || limit !== state.limit || offset !== state.offset || goalId!==state.goalSelection||selected!==state.selected) return result;
    if (!result.ok) { notify(errorText(result)); return result; }
    if(state.noticeKind==='connection')notify();
    state.snapshot = result.data;
    if (!state.selected && result.data.status.registrations.length) state.selected = result.data.status.registrations[0].id;
    await readSelection();
    // Files can change without a SQLite revision; displayed claims must recheck current integrity.
    if (state.scene === 'overview') await readOverviewMemory(name);
    if (state.scene === 'memory') {
      const memory = await core('research_memory', {...state.memoryArgs, workspace: name});
      if (name === state.workspace) state.memory = memory.ok ? memory.data : null;
    }
    if (['comparison','graph','stability'].includes(state.scene)) await readComparison();
    if (state.scene === 'evidence' && state.evidence) {
      const evidence = await request(`/api/evidence?${qs({workspace: name, registration: state.selected, evidence: state.evidence.evidence.id})}`);
      if (name === state.workspace && evidence.ok) state.evidence = evidence.data;
      else if (name === state.workspace && !evidence.ok) { state.evidence = null; notify(errorText(evidence)); }
    }
    $('updated-label').textContent = `${time(Date.now() / 1000)} 조회 · 읽기 상태 동기화`;
    drawOverview(); if (state.scene === 'memory') drawMemory(); if (state.scene === 'evidence') drawEvidence(); return result;
  })();
  try { return await state.refreshing; } finally { state.refreshing = null; }
}
function validatePresentation(name, args) {
  const tool = presentationTools.find((item) => item.name === name), properties = tool.inputSchema.properties;
  for (const key of Object.keys(args)) if (!(key in properties)) throw new Error(`Unknown field: ${key}`);
  for (const key of tool.inputSchema.required || []) if (typeof args[key] !== 'string' || !args[key]) throw new Error(`Required text: ${key}`);
  for (const [key, value] of Object.entries(args)) {
    const schema = properties[key], types = Array.isArray(schema.type) ? schema.type : [schema.type];
    if (!types.some((type) => type === 'null' ? value === null : type === 'integer' ? Number.isInteger(value) : type === 'array' ? Array.isArray(value) : typeof value === type)) throw new Error(`Invalid type: ${key}`);
    if (schema.enum && !schema.enum.includes(value)) throw new Error(`Invalid value: ${key}`);
    if (schema.minimum !== undefined && value < schema.minimum || schema.maximum !== undefined && value > schema.maximum) throw new Error(`Out of range: ${key}`);
    if (schema.maxLength && value.length > schema.maxLength) throw new Error(`Too long: ${key}`);
    if (schema.maxItems && value.length > schema.maxItems) throw new Error(`Too many records: ${key}`);
    if (key === 'compare') {
      if (!['comparison','graph','stability'].includes(args.scene)) throw new Error('compare requires comparison, graph or stability scene.');
      for (const item of value) if (!item || typeof item !== 'object' || Array.isArray(item) ||
        Object.keys(item).some(field => !['workspace', 'registration'].includes(field)) ||
        !relativeWorkspace(item.workspace) || typeof item.registration !== 'string' || !item.registration) throw new Error('Invalid comparison record.');
    }
  }
}
async function present(name, args) {
  if (name === 'research_view') {
    state.limit = args.limit ?? PAGE; state.offset = args.offset ?? 0;
    if(args.registration&&!args.goal)state.goalSelection='';
    if(args.goal&&args.goal!==state.goalSelection){state.goalSelection=args.goal;state.goal=null;state.records=[];if(!args.registration){state.selected='';state.record=null;state.summary=null;}}
    state.focus=args.focus||'';
    if (['comparison','graph','stability'].includes(args.scene)) { state.compareArgs = args.compare || null; state.records = []; state.compareMissing = []; }
    if (args.registration && args.registration !== state.selected) { state.selected = args.registration; state.record = null; state.summary = null; }
    setScene(args.scene || 'overview'); const snapshot = await refresh(); if (!snapshot?.ok) return snapshot;
    if (args.registration && !state.record) return envelopeError('NOT_FOUND', 'Selected registration could not be displayed.');
    if (state.scene === 'memory') {
      state.memoryArgs = {query: args.query ?? '', outcome: args.outcome ?? null, verification: args.verification ?? null, limit: state.limit, offset: state.offset};
      const result = await core('research_memory', {...state.memoryArgs, workspace: state.workspace}); if (!result.ok) return result;
      state.memory = result.data; drawMemory(); return {ok: true, data: {presentation: getViewState(), memory: result.data}};
    }
    const viewModel=model();return {ok: true, data: {presentation: getViewState(), viewModel, clientBrief:state.scene==='overview'?buildClientView(viewModel,{goal:state.snapshot?.report?.goal||state.goal}):undefined, comparisons: state.scene === 'comparison' ? compareRecords(state.records) : undefined, status: status(), events: state.scene === 'activity' ? state.snapshot.events : undefined}};
  }
  state.goalSelection=''; state.selected = args.registration;
  state.evidence = null; setScene('evidence');
  const selected = await refresh(); if (!selected.ok) return selected;
  if(!state.record)return envelopeError('NOT_FOUND','Selected registration could not be displayed.');
  const result = await request(`/api/evidence?${qs({workspace: state.workspace, registration: args.registration, evidence: args.evidence})}`);
  if (!result.ok) { render(); return result; }
  state.evidence = result.data; render(); return {ok: true, data: {...result.data, presentation: getViewState(), sourceReferences: model().refs}};
}
/** Native WebMCP is the action entry point. Background refresh only reads. */
export async function executeTool(name, parameters = {}) {
  if (!parameters || typeof parameters !== 'object' || Array.isArray(parameters)) return envelopeError('INVALID_INPUT', 'Arguments must be a JSON object.');
  const isPresentation = presentationTools.some((item) => item.name === name);
  if (!isPresentation && !state.tools.some((item) => item.name === name)) return envelopeError('INVALID_INPUT', 'Unknown page tool.');
  const args = {...parameters, workspace: parameters.workspace ?? (isPresentation ? state.workspace || 'default' : 'default')};
  try { finiteJson(args); if (!relativeWorkspace(args.workspace)) throw new Error('Workspace must be a relative name within the fixed root.'); if (isPresentation) validatePresentation(name, args); }
  catch (error) { return envelopeError('INVALID_INPUT', error.message); }
  const boot = await ensureSession(); if (!boot.ok) return boot;
  const call = {id: ++state.serial, tool: name, workspace: args.workspace, created: new Date().toISOString(), result: null};
  state.latest = call.id; state.calls.unshift(call); state.calls = state.calls.slice(0, 30); state.pending++;
  workspace(args.workspace); state.explanation = isPresentation ? args.explanation || '' : '';
  if (!isPresentation) setScene(name === 'research_memory' ? 'memory' : ['research_help', 'research_export', 'research_restore', 'research_laya_prepare', 'research_laya_resolve'].includes(name) ? 'activity' : 'overview');
  if(args.registration&&!args.goal)state.goalSelection='';
  if (args.registration && state.selected !== args.registration) { state.selected = args.registration; state.record = null; state.summary = null; }
  notify(); drawOverview(); drawCalls(); agentPhase(call, 'running'); let result;
  try {
    result = isPresentation ? await present(name, args) : await core(name, args);
    if (result.ok && state.latest === call.id && state.workspace === args.workspace && !isPresentation) {
      const data = result.data;
      if (args.goal||data?.goal?.id||name==='research_goal'){
        const goalId=args.goal||data?.goal?.id||(name==='research_goal'?data?.id:null);
        if(goalId&&goalId!==state.goalSelection){state.goalSelection=goalId;state.selected='';state.record=null;state.summary=null;state.goal=null;state.records=[];}
      }
      if (name === 'research_status') { state.limit = args.limit ?? PAGE; state.offset = args.offset ?? 0; }
      if (name === 'research_memory') { state.memory = data; state.memoryArgs = {query: args.query || '', outcome: args.outcome || null, verification: args.verification || null, limit: args.limit ?? PAGE, offset: args.offset ?? 0}; drawMemory(); }
      const record = data?.registration?.spec && data?.hypothesis ? data : null;
      const registration = record?.registration?.id || data?.record?.registration?.id || (name === 'research_register' ? data?.registration?.id : null) || args.registration;
      if (registration) { state.selected = registration; state.record = record; state.summary = null;
        state.goalSelection=record?.registration?.goal_id||data?.record?.registration?.goal_id||data?.registration?.goal_id||args.goal||''; }
      if (name === 'research_register' && !data.reused) state.offset = Math.floor((status().total || 0) / state.limit) * state.limit;
      if (name !== 'research_help') await refresh();
    }
  } catch (error) { result = envelopeError('CLIENT_ERROR', error.message); }
  call.result = result; state.pending--;
  if (result.ok && result.data?.presentation) result.data.presentation = getViewState();
  drawCalls();
  if (state.latest === call.id) { if (!result.ok) notify(errorText(result)); agentPhase(call, result.ok ? 'succeeded' : 'error'); } return result;
}
async function registerNativeTools() {
  const list = [...state.tools, ...presentationTools], node = $('webmcp-status');
  if (typeof document.modelContext?.registerTool !== 'function') { node.textContent = 'WebMCP 미지원 · 관전만 가능'; notify('이 브라우저에서는 에이전트의 웹 제어를 사용할 수 없습니다. 네이티브 WebMCP 지원 브라우저에서 이 페이지를 여세요. CLI 상태 변화는 계속 관전합니다.'); return; }
  let count = 0; const failures = [];
  for (const tool of list) { try { await document.modelContext.registerTool({name: tool.name, description: tool.description, inputSchema: tool.inputSchema, annotations: {readOnlyHint: Boolean(tool.annotations?.readOnlyHint)}, execute: async (args) => executeTool(tool.name, args || {})}); count++; } catch (error) { failures.push(`${tool.name}: ${error.message}`); } }
  node.textContent = `NATIVE WebMCP · ${count}/${list.length}`; node.dataset.state = count === list.length ? 'connected' : 'partial'; if (failures.length) notify(failures.join(' · '));
}
async function autoSelectWorkspace() {
  const result = await request(`/api/workspaces?${qs({limit: PAGE, offset: 0})}`); if (!result.ok) return;
  let saved = ''; try { saved = localStorage.getItem('research-state-workspace') || ''; } catch (_) { /* Optional only. */ }
  const items = result.data.items || [], preferred = items.find((item) => item.name === saved) || [...items].sort((a, b) => b.revision - a.revision)[0]; if (preferred) workspace(preferred.name);
}
async function start() {
  document.body.dataset.phase = 'idle'; setScene('overview'); agentPhase(null, 'idle'); drawOverview(); drawMemory(); drawCalls();
  const result = await ensureSession();
  if (result.ok) { state.tools = result.data.tools; await autoSelectWorkspace(); await refresh(); await registerNativeTools(); state.booted = true; }
  else { notify(errorText(result)); $('webmcp-status').textContent = 'WebMCP · 서버 연결 대기'; }
  // No automatic init, run, recovery mutation, verification, scientific choice, or model call.
  setInterval(async () => {
    if (document.visibilityState === 'hidden') return;
    if (!state.booted) { const boot = await ensureSession(); if (!boot.ok) return; state.tools = boot.data.tools; await autoSelectWorkspace(); await registerNativeTools(); state.booted = true; }
    if (!state.workspace) await autoSelectWorkspace(); await refresh();
  }, 2000);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') refresh(); });
  window.addEventListener('resize', drawGraph);
}
start();
