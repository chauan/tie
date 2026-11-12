'use strict';
const $=id=>document.getElementById(id),NS='http://www.w3.org/2000/svg',M=ReplayModel;
const loadedUIRevision=document.querySelector('meta[name="isle-ui-revision"]')?.content;
let state=null,calibration=null,playerProfile=null,viewReplay=null,archiveId='',viewTime=null;
let selected=null,selectedIdentity=null,showPlayers=true,showAI=true,offline=false,initializedMap=false;
let view={x:0,y:0,width:3900,height:3908},frameCache=null,frameCacheKey='',loadingReplayId=null,loadToken=0;
let frameGeneration=0,profileRequestToken=0;
let aiDensitySettings={enabled:true,cellMeters:500,species:''},aiDensityCache=null,aiDensityCacheKey='',aiDensitySelected=null,aiDensityExpanded=false;
try{const saved=JSON.parse(localStorage.getItem('isle-ai-density')||'null');if(saved&&typeof saved==='object'){if(typeof saved.enabled==='boolean')aiDensitySettings.enabled=saved.enabled;if([250,500,1000].includes(saved.cellMeters))aiDensitySettings.cellMeters=saved.cellMeters;if(typeof saved.species==='string')aiDensitySettings.species=saved.species;}}catch(_){}
let playing=false,playbackLast=0,measurementMode=false,measurementPoints=[],drag=null,suppressMapClick=false,followKey=null;
try{followKey=JSON.parse(localStorage.getItem('isle-follow-target')||'null');}catch(_){}
let proximitySettings={enabled:true,radius:500,kind:'all',arrows:true,sound:false,ignoreFriends:true};
try{const saved=JSON.parse(localStorage.getItem('isle-proximity')||'null');if(saved&&typeof saved==='object'){for(const key of['enabled','arrows','sound','ignoreFriends'])if(typeof saved[key]==='boolean')proximitySettings[key]=saved[key];if(Number.isFinite(saved.radius))proximitySettings.radius=Math.min(5000,Math.max(10,saved.radius));if(['all','player','ai'].includes(saved.kind))proximitySettings.kind=saved.kind;}}catch(_){}
let teammates=[],alertJournal={entries:[],tracking:{recording:null,levels:{}}},journalStorageFailed=false;
try{const saved=JSON.parse(localStorage.getItem('isle-teammates')||'[]');if(Array.isArray(saved))teammates=[...new Map(saved.filter(t=>t&&typeof t.steam_id==='string'&&/^\d{17}$/.test(t.steam_id)).slice(0,100).map(t=>[t.steam_id,{steam_id:t.steam_id,name:String(t.name||'').slice(0,60)}])).values()];}catch(_){}
let proximityCache=null,proximityCacheKey='',proximityAudio=null,proximityAlertSerial=0,teammateRevision=0,filterCacheKey='',filterCache=[],lastMarkerScale=null;
const svg=$('mapSvg');
const vnTime=new Intl.DateTimeFormat('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
const vnDate=new Intl.DateTimeFormat('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',day:'2-digit',month:'2-digit',year:'numeric'});
const number=value=>Number(value).toLocaleString('vi-VN',{maximumFractionDigits:1});
const clock=seconds=>{const s=Math.max(0,Math.floor(seconds));return s>=3600?`${String(Math.floor(s/3600)).padStart(2,'0')}:${String(Math.floor(s/60)%60).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`:`${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;};
const distanceText=meters=>meters>=1000?`${number(meters/1000)} km`:`${number(meters)} m`;
const element=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};
const svgEl=(tag,attrs={})=>{const e=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);return e;};
function currentTime(){return viewReplay?Math.min(viewReplay.time_seconds,Math.max(0,viewTime??viewReplay.time_seconds)):0;}
function allEntities(){if(!viewReplay)return[];const key=`${viewReplay.id}:${currentTime()}`;if(frameCacheKey!==key){frameCache=M.frameEntities(viewReplay,currentTime());frameCacheKey=key;frameGeneration++;}return frameCache||[];}
function position(e){if(!calibration||!M.hasPosition(e))return null;const p=GatewayProjection.worldToPixel(e,calibration);return p.x>=0&&p.x<=calibration.image_width&&p.y>=0&&p.y<=calibration.image_height?p:null;}
function isSelf(e){return !!playerProfile?.steam_id&&e.steam_id===playerProfile.steam_id;}
function profileLabel(){return playerProfile?.name||currentProximity().owner?.name||playerProfile?.steam_id||'tài khoản đã chọn';}
function journalKey(){return `isle-radar-journal:${playerProfile?.steam_id||'unselected'}`;}
function loadProfileJournal(profile){
  alertJournal={entries:[],tracking:{recording:null,levels:{}}};
  try{let raw=localStorage.getItem(journalKey());if(!raw&&profile.migrated_legacy)raw=localStorage.getItem('isle-radar-journal');const saved=JSON.parse(raw||'null');if(saved&&Array.isArray(saved.entries)){alertJournal.entries=saved.entries.filter(e=>e&&typeof e.id==='string'&&/^snapshot-\d+$/.test(e.snapshot_id)&&Number.isFinite(e.replay_time)&&e.replay_time>=0&&[1,2,3].includes(e.level)&&Number.isFinite(e.distance)&&Number.isFinite(e.min_distance)&&Number.isFinite(Date.parse(e.detected_at))).slice(0,200);if(saved.tracking&&typeof saved.tracking.recording==='string'&&saved.tracking.levels&&typeof saved.tracking.levels==='object')alertJournal.tracking=saved.tracking;}}catch(_){}
}
function applyProfile(profile){
  if(!profile||playerProfile&&profile.steam_id===playerProfile.steam_id&&profile.name===playerProfile.name)return;
  const oldId=playerProfile?.steam_id;playerProfile=profile;loadProfileJournal(profile);proximityCacheKey='';filterCacheKey='';
  if(followKey?.steam_id===oldId&&profile.steam_id)saveFollow({...followKey,steam_id:profile.steam_id,name:profile.name||profile.steam_id});
  $('profileSteam').value=profile.steam_id||'';$('profileName').value=profile.name||'';$('profileCurrent').textContent=profile.steam_id?`Đang chọn ${profile.name||profile.steam_id}`:'Chưa chọn tài khoản';$('profileClear').disabled=!profile.steam_id;$('meBtn').disabled=!profile.steam_id;
  renderEntities();
}
async function chooseProfile(steamId,name=''){
  profileRequestToken++;$('profileError').textContent='';$('profileSave').disabled=true;
  try{const profile=await post('/api/profile',{steam_id:String(steamId).trim(),name:String(name).trim()});if(state)state.player_profile=profile;applyProfile(profile);toast(profile.steam_id?'Đã chọn tài khoản làm tâm radar.':'Đã bỏ chọn tài khoản.');return true;}catch(error){$('profileError').textContent=error.message;return false;}finally{$('profileSave').disabled=false;}
}
function isTeammate(e){return e.kind==='player'&&!isSelf(e)&&teammates.some(t=>t.steam_id===e.steam_id);}
function speciesName(e){return({Coalecanth:'Coelacanth',Fish_Coalacanth:'Cá trong đàn',Deer:'Hươu'})[e.species]||e.species||'Chưa rõ loài';}
function growthText(e){return Number.isFinite(e.growth)&&e.growth>=0&&e.growth<=1?`${number(e.growth*100)}% trưởng thành`:'Trưởng thành chưa rõ';}
function dinoDescription(e){return `${speciesName(e)} · ${growthText(e)}`;}
function teammateName(e){return teammates.find(t=>t.steam_id===e.steam_id)?.name||e.name||e.steam_id;}
function levelName(level){return ['Ngoài bán kính','Chú ý','Ở gần','Rất gần'][level]||'Chú ý';}
function displayName(e){const name=e.name||(e.kind==='player'?e.steam_id||`Người chơi #${e.id}`:`${speciesName(e)} #${e.id}`);return isSelf(e)?`${name} (Bạn)`:name;}
function currentProximity(){const entities=allEntities(),key=`${frameCacheKey}:${frameGeneration}:${playerProfile?.steam_id}:${proximitySettings.radius}:${proximitySettings.kind}:${proximitySettings.ignoreFriends}:${teammateRevision}`;if(key!==proximityCacheKey){proximityCache=M.proximity(entities,playerProfile?.steam_id,{...proximitySettings,friendIds:teammates.map(t=>t.steam_id)});proximityCacheKey=key;}return proximityCache;}
function relativeToMe(e){const report=currentProximity();return report.available&&!isSelf(e)?M.relativePosition(report.owner,e):null;}
function directionText(relative){return relative.bearing===null?relative.direction:`${relative.direction} · ${Math.round(relative.bearing)%360}°`;}
function directionArrow(relative){const arrow=element('span','direction-arrow',relative.bearing===null?'•':'↑');if(relative.bearing!==null)arrow.style.transform=`rotate(${relative.bearing}deg)`;arrow.setAttribute('aria-hidden','true');return arrow;}
function liveProximity(){return !!viewReplay&&!archiveId&&viewTime===null&&!playing&&viewReplay.id===state?.replay?.id&&!offline;}
function prepareProximityAudio(){if(!proximitySettings.sound)return;try{const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)return;proximityAudio ||=new Audio();proximityAudio.resume().catch(()=>{});}catch(_){} }
function playProximitySound(level=1){if(!proximitySettings.sound||proximityAudio?.state!=='running')return;try{const now=proximityAudio.currentTime,count=Math.max(1,Math.min(3,level));for(let i=0;i<count;i++){const at=now+i*.2,tone=proximityAudio.createOscillator(),gain=proximityAudio.createGain();tone.type='sine';tone.frequency.value=420+level*160+i*90;gain.gain.setValueAtTime(0,at);gain.gain.linearRampToValueAtTime(.12,at+.015);gain.gain.exponentialRampToValueAtTime(.001,at+.14);tone.connect(gain);gain.connect(proximityAudio.destination);tone.start(at);tone.stop(at+.16);tone.onended=()=>{tone.disconnect();gain.disconnect();};}}catch(_){} }
function persistAlertJournal(){try{localStorage.setItem(journalKey(),JSON.stringify(alertJournal));journalStorageFailed=false;}catch(_){journalStorageFailed=true;}}
function alertProximity(report){
  if(!liveProximity()||!proximitySettings.enabled)return;
  const recording=`${viewReplay.filename}:${viewReplay.recorded_at}`;
  if(recording!==alertJournal.tracking.recording||currentTime()<(alertJournal.tracking.replay_time||0)-.01)alertJournal.tracking={recording,levels:{}};
  const before=JSON.stringify(alertJournal.tracking),transition=M.proximityTransitions(alertJournal.tracking.levels,report.available?report.alerts:[],report.radius);
  for(const event of transition.events){const e=event.target.entity,tracked=transition.next[event.key];tracked.episode ||=crypto.randomUUID();const entry={id:crypto.randomUUID(),episode:tracked.episode,type:event.type,level:event.level,detected_at:new Date().toISOString(),snapshot_id:viewReplay.id,filename:viewReplay.filename,recorded_at:viewReplay.recorded_at,replay_time:currentTime(),entity_id:e.id,steam_id:e.steam_id,name:e.name,species:e.species,growth:e.growth,kind:e.kind,friendly:event.target.friendly,distance:event.target.distance,min_distance:tracked.min_distance,direction:event.target.direction,bearing:event.target.bearing};alertJournal.entries.unshift(entry);}
  let changed=transition.events.length>0;
  const activeEpisodes=new Map(Object.values(transition.next).filter(t=>t.episode).map(t=>[t.episode,t.min_distance]));
  for(const entry of alertJournal.entries){const minimum=activeEpisodes.get(entry.episode);if(minimum!==undefined&&minimum<entry.min_distance){entry.min_distance=minimum;changed=true;}}
  alertJournal.entries=alertJournal.entries.slice(0,200);alertJournal.tracking={recording,replay_time:currentTime(),levels:transition.next};
  if(changed||before!==JSON.stringify(alertJournal.tracking))persistAlertJournal();
  if(!transition.events.length)return;proximityAlertSerial++;const first=transition.events[0],target=first.target;toast(`${levelName(first.level)} · ${displayName(target.entity)} · ${dinoDescription(target.entity)} · cách ${profileLabel()} ${distanceText(target.distance)} · ${target.direction}${transition.events.length>1?` · +${transition.events.length-1} đối tượng`:''}.`);$('toast').dataset.level=first.level;playProximitySound(first.level);
}
function renderAlertLog(){
  const entries=alertJournal.entries,list=$('alertLog'),signature=JSON.stringify(entries);$('alertLogCount').textContent=entries.length;$('clearAlertLog').disabled=!entries.length;if(list.dataset.signature===signature)return;list.dataset.signature=signature;list.replaceChildren();
  if(!entries.length){list.append(element('p','tool-hint','Chưa có cảnh báo. Nhật ký bắt đầu khi mục tiêu được ghi nhận ở cuối replay mới nhất.'));return;}
  for(const entry of entries){const button=element('button','alert-log-row');button.dataset.entryId=entry.id;button.dataset.level=entry.level;const heading=element('span','alert-log-row-heading');heading.append(element('span',`radar-level level-${entry.level}`,`${levelName(entry.level)} · ${entry.type==='closer'?'Vào mức gần hơn':'Vào bán kính'}`),element('span','',vnTime.format(new Date(entry.detected_at))));button.append(heading,element('strong','',`${entry.name||entry.steam_id||`AI #${entry.entity_id}`} · ${dinoDescription(entry)}`),element('span','',`${entry.kind==='player'?'Người chơi':'AI'}${entry.friendly?' · Đồng đội':''} · ${distanceText(entry.distance)} · ${entry.direction} · Gần nhất đã ghi: ${distanceText(entry.min_distance)}`),element('span','alert-log-source',`${vnDate.format(new Date(entry.detected_at))} · ${entry.filename} · mốc ${clock(entry.replay_time)} ↗`));button.onclick=()=>jumpToAlert(entry);list.append(button);}
}
async function jumpToAlert(entry){
  if(!state?.history?.some(r=>r.id===entry.snapshot_id)&&state?.replay?.id!==entry.snapshot_id){toast('Bản sao này đã hết thời gian lưu. Thông tin cảnh báo vẫn còn trong nhật ký.');return;}
  playing=false;archiveId=entry.snapshot_id;viewTime=entry.replay_time;renderHistory();await loadReplay(entry.snapshot_id);if(viewReplay?.id!==entry.snapshot_id)return;setTime(entry.replay_time);const e=M.followTarget(allEntities(),{steam_id:entry.steam_id,entity_id:entry.entity_id});if(e){$('resetFilters').click();if(!e.in_scope||e.dead)$('historyToggle').checked=true;selectEntity(e.id);}else toast('Đã mở mốc cảnh báo; mục tiêu không có dữ liệu ở mốc này.');
}
function renderTeammates(){
  $('teammateCount').textContent=teammates.length;const list=$('teammateList');list.replaceChildren();if(!teammates.length)list.append(element('p','tool-hint','Chưa lưu đồng đội. Có thể thêm SteamID ở đây hoặc chọn một người chơi trên bản đồ.'));
  for(const friend of teammates){const row=element('div','teammate-item'),text=element('span','teammate-item-text');text.append(element('strong','',friend.name||'Đồng đội'),element('span','',friend.steam_id));const remove=element('button','text-button small','Bỏ');remove.type='button';remove.setAttribute('aria-label',`Bỏ đồng đội ${friend.name||friend.steam_id}`);remove.onclick=()=>removeTeammate(friend.steam_id);row.append(text,remove);list.append(row);}
}
function storeTeammates(){
  teammateRevision++;proximityCacheKey='';try{localStorage.setItem('isle-teammates',JSON.stringify(teammates));}catch(_){$('teammateError').textContent='Đã áp dụng trong phiên này; trình duyệt chưa lưu được danh sách.';}renderTeammates();renderEntities();
}
function saveTeammate(steamId,name){
  $('teammateError').textContent='';steamId=String(steamId).trim();if(!/^\d{17}$/.test(steamId)){$('teammateError').textContent='SteamID cần đúng 17 chữ số.';return false;}if(steamId===playerProfile?.steam_id){$('teammateError').textContent='Đây là SteamID đang làm tâm radar, đã được đánh dấu là bạn.';return false;}
  const old=teammates.find(t=>t.steam_id===steamId);if(!old&&teammates.length>=100){$('teammateError').textContent='Đã lưu đủ 100 đồng đội. Bỏ một mục trước khi thêm.';return false;}if(old)old.name=String(name).trim().slice(0,60);else teammates.push({steam_id:steamId,name:String(name).trim().slice(0,60)});storeTeammates();return true;
}
function removeTeammate(steamId){teammates=teammates.filter(t=>t.steam_id!==steamId);$('teammateError').textContent='';storeTeammates();}
function renderProximity(){
  const report=currentProximity(),panel=$('proximityPanel'),live=liveProximity(),summary=$('proximitySummary'),list=$('nearbyList');
  const maximum=report.alerts.reduce((level,t)=>Math.max(level,M.proximityLevel(t.distance,report.radius)),0);
  panel.classList.toggle('nearby-warning',report.available&&proximitySettings.enabled&&maximum>0);panel.classList.toggle('proximity-unavailable',!report.available);panel.dataset.level=proximitySettings.enabled?maximum:0;$('nearbyFocusBtn').disabled=!report.available;
  $('proximityMode').textContent=live?'CUỐI REPLAY':'XEM LẠI';$('proximityMode').classList.toggle('archived',!live);
  const players=report.nearby.filter(t=>t.entity.kind==='player').length,ai=report.nearby.length-players;
  const friends=report.nearby.filter(t=>t.friendly).length;
  const message=!report.available?!playerProfile?.steam_id?'Nhập SteamID để chọn tài khoản làm tâm radar.':!report.owner?'Replay chưa có vị trí tài khoản đã chọn ở thời điểm này.':report.owner.dead?'Tài khoản đã chọn đã chết ở mốc này; dừng cảnh báo.':'Replay đã mất dấu tài khoản đã chọn; dừng cảnh báo vị trí cũ.':report.nearby.length?`${players} người chơi · ${ai} AI trong ${distanceText(report.radius)} quanh bạn${friends?` · ${friends} đồng đội${proximitySettings.ignoreFriends?' được bỏ cảnh báo':''}`:''}`:`Chưa thấy đối tượng phù hợp trong ${distanceText(report.radius)} quanh bạn`;
  if(summary.textContent!==message)summary.textContent=message;
  if($('radarLevels').dataset.radius!==String(report.radius)){$('radarLevels').dataset.radius=report.radius;$('radarLevels').replaceChildren();for(const [level,limit]of[[1,report.radius],[2,Math.min(250,report.radius)],[3,Math.min(100,report.radius)]]){if(level===1&&report.radius<=250||level===2&&report.radius<=100)continue;const badge=element('span',`radar-level level-${level}`,`${levelName(level)} ≤ ${distanceText(limit)}`);$('radarLevels').append(badge);}}
  const listSignature=teammateRevision+':'+JSON.stringify(report.nearby.map(t=>[t.entity.id,t.entity.name,t.entity.species,t.entity.growth,t.distance,t.bearing,t.friendly]));if(list.dataset.signature!==listSignature){list.dataset.signature=listSignature;list.replaceChildren();
  for(const target of report.nearby.slice(0,8)){const button=element('button',`nearby-target${target.friendly?' teammate':''}`);button.dataset.entityId=target.entity.id;button.dataset.level=M.proximityLevel(target.distance,report.radius);button.append(directionArrow(target));const text=element('span','nearby-target-text');text.append(element('strong','',target.friendly?`${teammateName(target.entity)} · Đồng đội`:displayName(target.entity)),element('span','nearby-dino',dinoDescription(target.entity)),element('span','',`${target.entity.kind==='player'?'Người chơi':'AI'} · ${distanceText(target.distance)} · ${directionText(target)}`));button.append(text);button.onclick=()=>{const e=target.entity;if(!M.matchesFilters(e,filters())){$('resetFilters').click();}selectEntity(e.id);};list.append(button);}
  if(report.nearby.length>8)list.append(element('span','nearby-more',`+${report.nearby.length-8} đối tượng khác trong bán kính`));}
  const hint=`${proximitySettings.enabled?'Cảnh báo bật':'Cảnh báo tắt'} · Khoảng cách X/Y; Bắc ở trên bản đồ. ${live?'Dữ liệu cuối replay, cập nhật mỗi '+(state?.interval_seconds||180)+' giây.':'Đang xem lại; không phát âm cảnh báo.'} Bộ lọc bản đồ không tắt cảnh báo.${proximitySettings.sound&&proximityAudio?.state!=='running'?' Bấm vào trang để cho phép âm thanh.':''}`;
  const storageHint=journalStorageFailed?' Nhật ký chỉ đang giữ trong phiên này vì trình duyệt không lưu được.':'';
  if($('proximityHint').textContent!==hint+storageHint)$('proximityHint').textContent=hint+storageHint;alertProximity(report);renderAlertLog();
}
function drawProximity(){
  const group=$('proximityOverlay');group.replaceChildren();const report=currentProximity();if(!calibration||!proximitySettings.arrows||!report.available)return;const origin=position(report.owner);if(!origin)return;
  const scale=view.width/Math.max(1,svg.clientWidth),east=GatewayProjection.worldToPixel({x:report.owner.x+report.radius*100,y:report.owner.y},calibration),south=GatewayProjection.worldToPixel({x:report.owner.x,y:report.owner.y+report.radius*100},calibration);
  group.append(svgEl('ellipse',{cx:origin.x,cy:origin.y,rx:Math.abs(east.x-origin.x),ry:Math.abs(south.y-origin.y),class:'proximity-radius','stroke-width':1.4*scale,'stroke-dasharray':`${5*scale} ${5*scale}`}));
  const visible=new Set(filteredEntities().map(e=>e.id)),targets=report.nearby.filter(t=>visible.has(t.entity.id)),chosen=selectedEntity();if(chosen&&!isSelf(chosen)&&chosen.in_scope&&!chosen.dead&&!targets.some(t=>t.entity.id===chosen.id)){const relative=relativeToMe(chosen);if(relative)targets.push({entity:chosen,...relative});}
  for(const target of targets){const p=position(target.entity);if(!p||target.bearing===null)continue;const dx=p.x-origin.x,dy=p.y-origin.y,length=Math.hypot(dx,dy),ux=dx/length,uy=dy/length;if(length<20*scale)continue;const tip={x:p.x-ux*10*scale,y:p.y-uy*10*scale},base={x:tip.x-ux*8*scale,y:tip.y-uy*8*scale},color=isTeammate(target.entity)?'#83caff':target.entity.kind==='ai'?'#ffcd7d':'#b2ffd0';
    group.append(svgEl('line',{x1:origin.x+ux*12*scale,y1:origin.y+uy*12*scale,x2:base.x,y2:base.y,stroke:color,'stroke-width':1.4*scale,'stroke-dasharray':`${4*scale} ${4*scale}`,class:'proximity-line','data-entity-id':target.entity.id}),svgEl('polygon',{points:`${tip.x},${tip.y} ${base.x-uy*4*scale},${base.y+ux*4*scale} ${base.x+uy*4*scale},${base.y-ux*4*scale}`,fill:color,class:'proximity-arrow','data-bearing':target.bearing,'data-entity-id':target.entity.id}));
  }
}
function filters(){return{history:$('historyToggle').checked,players:showPlayers,ai:showAI,query:$('search').value,species:$('speciesFilter').value,status:$('statusFilter').value,minGrowth:Number($('growthMin').value||0),maxGrowth:Number($('growthMax').value||100)};}
function filteredEntities(){const entities=allEntities(),f=filters(),key=`${frameCacheKey}:${frameGeneration}:${playerProfile?.steam_id}:${JSON.stringify(f)}`;if(key!==filterCacheKey){filterCacheKey=key;filterCache=entities.filter(e=>M.matchesFilters(e,f)).sort((a,b)=>Number(isSelf(b))-Number(isSelf(a))||(a.kind==='player'?0:1)-(b.kind==='player'?0:1)||(a.name||a.species||'').localeCompare(b.name||b.species||'')||a.id-b.id);}return filterCache;}
function toast(message){$('toast').textContent=message;$('toast').hidden=false;delete $('toast').dataset.level;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,6000);}
function detailPairs(container,rows){const grid=element('div','detail-grid');for(const[label,value]of rows)grid.append(element('span','',label),element('span','long',value));container.append(grid);}
function targetForFollow(){return M.followTarget(allEntities(),followKey);}
function selectedEntity(){return allEntities().find(e=>e.id===selected)||null;}
function activeRouteTarget(){return selectedEntity()||targetForFollow();}
function trailSegments(){const e=activeRouteTarget();return e&&$('trailToggle').checked?M.routeSegments(viewReplay,e.id,currentTime(),Number($('trailWindow').value)||Infinity):[];}
function saveFollow(key){followKey=key;try{if(key)localStorage.setItem('isle-follow-target',JSON.stringify(key));else localStorage.removeItem('isle-follow-target');}catch(_){}renderFollow();}
function centerOn(e){const p=e&&position(e);if(!p)return;view.x=p.x-view.width/2;view.y=p.y-view.height/2;updateView();}
function applyFollow(){const e=targetForFollow();if(e&&(e.in_scope&&!e.dead||$('historyToggle').checked))centerOn(e);renderFollow();}
function renderFollow(){const e=targetForFollow(),box=$('followStatus');$('stopFollowBtn').hidden=!followKey;$('followBtn').disabled=!selectedEntity();box.hidden=!followKey;if(!followKey)return;const lost=!e||!e.in_scope||e.dead;box.classList.toggle('lost',lost);box.textContent=!e?'Mục tiêu chưa xuất hiện tại thời điểm này.':lost?`${displayName(e)} · Thấy lần cuối ở ${clock(e.last_seen)}. Bật lịch sử để xem vị trí đã ghi.`:`Đang theo dõi ${displayName(e)} · ${speciesName(e)}`;}
function selectEntity(id,center=true){const e=allEntities().find(e=>e.id===id);selected=id;selectedIdentity=e?{steam_id:e.steam_id,entity_id:e.id}:null;if(center)centerOn(e);renderEntities();}
function drawDetails(){
  const e=selectedEntity(),detail=$('entityDetail');detail.replaceChildren();detail.hidden=!e;if(!e){renderFollow();return;}
  detail.append(element('h3','',displayName(e)));
  const rows=[['Loài',speciesName(e)],['Loại',e.kind==='player'?'Người chơi':e.kind==='ai'?'AI':'Chưa xác định'],['SteamID',e.steam_id||'—'],['X / Y (cm)',e.x!==null&&e.y!==null?`${number(e.x)} / ${number(e.y)}`:'—'],['Độ cao Z (cm)',e.z!==null?number(e.z):'—'],['Tăng trưởng',e.growth!==null?`${(e.growth*100).toFixed(1)}%`:'—'],['Thấy ở',clock(e.last_seen)],['Trạng thái',e.dead?'Đã chết':e.in_scope?'Trong phạm vi ghi':'Đã rời phạm vi']];
  if(viewReplay.tracks)rows.push(['Đường đã ghi',distanceText(M.routeDistance(trailSegments()))]);
  const relative=relativeToMe(e);
  if(relative){rows.push([e.in_scope&&!e.dead?'Cách tài khoản của bạn':'Điểm cuối cách tài khoản của bạn',distanceText(relative.distance)],['Hướng từ tài khoản của bạn',directionText(relative)]);}else if(!isSelf(e))rows.push(['Khoảng cách đến tài khoản của bạn','Chưa có vị trí hiện tại của bạn']);
  if(isTeammate(e))rows.push(['Đồng đội',teammateName(e)]);
  detailPairs(detail,rows);const actions=element('div','detail-actions'),follow=element('button','tool-button','◎ Theo dõi');follow.onclick=()=>startFollow(e);actions.append(follow);if(e.kind==='player'&&e.steam_id&&!isSelf(e)){const useMe=element('button','tool-button','Dùng làm tâm radar');useMe.onclick=()=>chooseProfile(e.steam_id,e.name||'');actions.append(useMe);}if(e.kind==='player'&&e.steam_id&&!isSelf(e)){const friend=element('button','tool-button',isTeammate(e)?'Bỏ đồng đội':'＋ Đồng đội');friend.onclick=()=>{if(isTeammate(e))removeTeammate(e.steam_id);else saveTeammate(e.steam_id,e.name||'');};actions.append(friend);}detail.append(actions);renderFollow();
}
function currentAiDensity(){
  const entities=allEntities(),key=`${frameGeneration}:${aiDensitySettings.cellMeters}:${aiDensitySettings.species}`;
  if(key!==aiDensityCacheKey){aiDensityCacheKey=key;aiDensityCache=M.aiDensity(entities,{...aiDensitySettings,bounds:calibration});}
  return aiDensityCache;
}
function saveAiDensitySettings(){try{localStorage.setItem('isle-ai-density',JSON.stringify(aiDensitySettings));}catch(_){} }
function updateAiDensitySpecies(){
  const select=$('aiDensitySpecies'),signature=viewReplay?.id||'';if(select.dataset.replay===signature)return;select.dataset.replay=signature;
  select.replaceChildren();const all=element('option','','Tất cả loài AI');all.value='';select.append(all);
  const species=[...new Set((viewReplay?.entities||[]).filter(e=>e.kind==='ai').map(e=>e.species||''))].sort();
  for(const name of species){if(!name)continue;const option=element('option','',speciesName({species:name}));option.value=name;select.append(option);}
  if(viewReplay&&!species.includes(aiDensitySettings.species))aiDensitySettings.species='';select.value=aiDensitySettings.species;
}
function aiCellLabel(cell){return `Ô ${cell.col+1}–${cell.row+1}`;}
function renderAiDensity(){
  updateAiDensitySpecies();const report=currentAiDensity(),proximity=currentProximity(),owner=proximity.available?proximity.owner:null;
  $('aiDensitySummary').textContent=!viewReplay?'Đang chờ dữ liệu replay.':`${number(report.total)} AI · ${report.cells.length} ô có AI · Mốc ${clock(currentTime())}${viewTime===null?' · cuối bản ghi':''}`;
  $('aiDensityFit').disabled=!report.cells.length;$('aiDensityMore').hidden=report.cells.length<=5;$('aiDensityMore').setAttribute('aria-expanded',String(aiDensityExpanded));$('aiDensityMore').textContent=aiDensityExpanded?'Thu gọn về 5 ô đông nhất':`Xem tất cả ${report.cells.length} ô`;
  const rows=(aiDensityExpanded?report.cells:report.cells.slice(0,5)).map(cell=>({cell,relative:owner?M.relativePosition(owner,cell):null}));
  const signature=JSON.stringify([aiDensitySelected,aiDensityExpanded,report.cellMeters,rows.map(({cell,relative})=>[cell.id,cell.count,cell.species,relative?distanceText(relative.distance)+' '+directionText(relative):''])]);
  const list=$('aiDensityList');if(list.dataset.signature===signature)return;list.dataset.signature=signature;list.replaceChildren();
  if(!rows.length){list.append(element('p','ai-density-empty',viewReplay?'Chưa có AI phù hợp đang trong phạm vi ghi ở mốc này.':'Chờ bản replay đầu tiên để thống kê.'));return;}
  rows.forEach(({cell,relative},index)=>{
    const button=element('button',`ai-density-card${cell.id===aiDensitySelected?' selected':''}`);button.type='button';button.dataset.cellId=cell.id;button.setAttribute('aria-pressed',String(cell.id===aiDensitySelected));
    const heading=element('span','ai-density-card-heading');heading.append(element('span','',`${String(index+1).padStart(2,'0')} · ${aiCellLabel(cell)}`),element('strong','',`${cell.count} AI`));
    const names=cell.species.slice(0,3).map(s=>`${speciesName({species:s.name})} ×${s.count}`).join(' · ')+(cell.species.length>3?` · +${cell.species.length-3} loài`:'');
    const direction=element('span','ai-density-direction');if(relative){direction.append(directionArrow(relative),document.createTextNode(`~${distanceText(relative.distance)} · ${relative.direction}`));}else direction.textContent='Chưa có vị trí của bạn ở mốc này';
    button.append(heading,element('span','ai-density-species',names),direction);button.onclick=()=>focusAiDensity(cell.id);list.append(button);
  });
}
function drawAiDensity(){
  const group=$('aiDensityOverlay');group.replaceChildren();if(!aiDensitySettings.enabled||!calibration)return;
  const report=currentAiDensity(),scale=view.width/Math.max(1,svg.clientWidth),fragment=document.createDocumentFragment();
  for(const cell of report.cells){
    const b=cell.bounds,a=GatewayProjection.worldToPixel({x:b.xMin,y:b.yMin},calibration),z=GatewayProjection.worldToPixel({x:b.xMax,y:b.yMax},calibration),ratio=cell.count/report.maxCount;
    const color=ratio>.66?'#fa775f':ratio>.33?'#f5ac5d':'#e8cf70',chosen=cell.id===aiDensitySelected;
    fragment.append(svgEl('rect',{class:'ai-density-cell','data-cell-id':cell.id,x:a.x,y:a.y,width:z.x-a.x,height:z.y-a.y,fill:color,'fill-opacity':.12+.3*ratio,stroke:chosen?'#d4ffe1':color,'stroke-opacity':chosen?1:.65,'stroke-width':(chosen?2.5:1)*scale}));
    if((z.x-a.x)/scale>=25){const label=svgEl('text',{x:(a.x+z.x)/2,y:(a.y+z.y)/2,'font-size':11*scale,'stroke-width':3*scale,'text-anchor':'middle','dominant-baseline':'central',class:'ai-density-count'});label.textContent=String(cell.count);fragment.append(label);}
  }group.append(fragment);
}
function focusAiDensity(id=null){
  const report=currentAiDensity(),cells=id?report.cells.filter(c=>c.id===id):report.cells;if(!cells.length||!calibration)return;
  aiDensitySelected=id;aiDensitySettings.enabled=true;$('aiDensityToggle').checked=true;saveAiDensitySettings();saveFollow(null);
  const xMin=Math.min(...cells.map(c=>c.bounds.xMin)),xMax=Math.max(...cells.map(c=>c.bounds.xMax)),yMin=Math.min(...cells.map(c=>c.bounds.yMin)),yMax=Math.max(...cells.map(c=>c.bounds.yMax));
  const a=GatewayProjection.worldToPixel({x:xMin,y:yMin},calibration),b=GatewayProjection.worldToPixel({x:xMax,y:yMax},calibration);fitBounds(a.x,a.y,b.x-a.x,b.y-a.y,id?1.65:1.15);drawAiDensity();renderAiDensity();$('mapContainer').scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
}
function renderEntities(){
  const entities=filteredEntities(),list=$('entityList');$('listCount').textContent=entities.length;list.replaceChildren();
  if(!entities.length)list.append(element('div','empty-list',viewReplay?'Không có đối tượng phù hợp ở thời điểm và bộ lọc này.':'Đang chờ dữ liệu replay.'));
  const fragment=document.createDocumentFragment();
  for(const e of entities){const ghost=!e.in_scope||e.dead,row=element('button',`entity-row${selected===e.id?' selected':''}${ghost?' ghost':''}${isTeammate(e)?' teammate':''}`);row.setAttribute('aria-pressed',String(selected===e.id));
    const avatar=element('span',`entity-avatar ${e.kind==='ai'?'ai':''}`,e.kind==='player'?'P':e.kind==='ai'?'AI':'?'),text=element('span','entity-text');text.append(element('span','entity-name',displayName(e)),element('span','entity-species',`${speciesName(e)}${e.growth!==null?` · ${Math.round(e.growth*100)}%`:''}`));
    const relative=relativeToMe(e);if(relative){const distance=element('span',`entity-distance${!ghost&&relative.distance<=proximitySettings.radius?' close':''}`);distance.append(directionArrow(relative),document.createTextNode(`${ghost?'Điểm cuối · ':''}${distanceText(relative.distance)} · ${relative.direction}`));text.append(distance);}
    const status=element('span',`entity-status ${e.kind==='ai'?'ai':''} ${ghost?'ghost':''}`,!position(e)?'CHƯA CÓ XY':e.dead?'ĐÃ CHẾT':!e.in_scope?'LẦN CUỐI':isTeammate(e)?'ĐỒNG ĐỘI':e.kind==='ai'?'AI':'NGƯỜI CHƠI');row.append(avatar,text,status);row.onclick=()=>selectEntity(e.id);fragment.append(row);
  }list.append(fragment);renderProximity();renderAiDensity();drawMarkers();drawDetails();
}
function drawMarkers(){
  const group=$('markers');group.replaceChildren();const scale=view.width/Math.max(1,svg.clientWidth),fragment=document.createDocumentFragment();lastMarkerScale=scale;
  for(const e of filteredEntities()){const p=position(e);if(!p)continue;const ghost=!e.in_scope||e.dead,color=ghost?'#aeb8b1':isTeammate(e)?'#83caff':e.kind==='ai'?'#ffcd7d':e.kind==='player'?'#b2ffd0':'#b5c2cc';
    const relative=relativeToMe(e),g=svgEl('g',{class:`marker${selected===e.id?' selected':''}${isSelf(e)?' self':''}${isTeammate(e)?' teammate':''}`,transform:`translate(${p.x} ${p.y})`,role:'button',tabindex:'0','aria-label':`${displayName(e)}, ${dinoDescription(e)}${relative?', cách '+profileLabel()+' '+distanceText(relative.distance)+', '+relative.direction:''}`});const title=svgEl('title');title.textContent=`${displayName(e)} · ${dinoDescription(e)}${isTeammate(e)?' · Đồng đội':''}\nX ${number(e.x)} / Y ${number(e.y)}\nThấy ở ${clock(e.last_seen)}${ghost?' · Vị trí lần cuối':''}${relative?'\nCách '+profileLabel()+' '+distanceText(relative.distance)+' · '+directionText(relative):''}`;
    const radius=(e.kind==='player'?5.5:3.5)*scale,hit=svgEl('circle',{r:12*scale,fill:'transparent'}),halo=svgEl('circle',{class:'halo',r:radius+4*scale,fill:color}),dot=svgEl('circle',{r:radius,fill:color,stroke:'#12291e','stroke-width':1.6*scale});if(ghost){dot.setAttribute('fill','#1f312ac0');dot.setAttribute('stroke',color);}g.append(title,hit,halo,dot);
    if(isSelf(e))g.append(svgEl('circle',{r:radius+2*scale,fill:'none',stroke:'#f4fff7','stroke-width':1.5*scale,'pointer-events':'none'}));
    if(selected===e.id||isSelf(e)){const label=svgEl('text',{x:12*scale,y:4*scale,'font-size':12*scale,class:'marker-label','stroke-width':3*scale});label.textContent=displayName(e)+(relative?` · ${distanceText(relative.distance)} · ${relative.direction}`:'');g.append(label);}
    g.onclick=event=>{event.stopPropagation();if(measurementMode)addMeasurement(e);else selectEntity(e.id,false);};g.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();if(measurementMode)addMeasurement(e);else selectEntity(e.id,false);}};fragment.append(g);
  }group.append(fragment);drawAiDensity();drawProximity();drawRoutes();drawMeasurements();
}
function drawRoutes(){
  const group=$('routes');group.replaceChildren();const segments=trailSegments(),scale=view.width/Math.max(1,svg.clientWidth),target=activeRouteTarget();
  for(const segment of segments){const points=segment.map(point=>GatewayProjection.worldToPixel(point,calibration)).map(p=>`${p.x},${p.y}`).join(' ');group.append(svgEl('polyline',{points,class:'route-shadow','stroke-width':5*scale}),svgEl('polyline',{points,class:'route-line','stroke-width':2*scale}));}
  if(segments.length){const p=GatewayProjection.worldToPixel(segments[0][0],calibration);group.append(svgEl('circle',{cx:p.x,cy:p.y,r:4*scale,class:'route-origin','stroke-width':1.5*scale}));}
  $('trailSummary').textContent=!target?'Chọn một đối tượng để xem đường di chuyển.':!viewReplay?.tracks?'Bản sao này chưa có lịch sử di chuyển.':!segments.length?'Chưa có đoạn đường trong khoảng đang xem.':`${displayName(target)} · ~${distanceText(M.routeDistance(segments))}`;
}
function drawMeasurements(){
  const group=$('measurements');group.replaceChildren();const scale=view.width/Math.max(1,svg.clientWidth),points=measurementPoints.map(p=>GatewayProjection.worldToPixel(p,calibration));
  if(points.length===2){const[a,b]=points;group.append(svgEl('line',{x1:a.x,y1:a.y,x2:b.x,y2:b.y,class:'measure-line','stroke-width':2*scale,'stroke-dasharray':`${6*scale} ${5*scale}`}));const label=svgEl('text',{x:(a.x+b.x)/2,y:(a.y+b.y)/2-8*scale,'font-size':12*scale,'stroke-width':4*scale,'text-anchor':'middle',class:'measure-label'});label.textContent=distanceText(M.distanceMeters(...measurementPoints));group.append(label);}
  for(const p of points)group.append(svgEl('circle',{cx:p.x,cy:p.y,r:4.5*scale,fill:'#fff0b8',stroke:'#192a1e','stroke-width':1.5*scale,'pointer-events':'none'}));
  $('clearMeasureBtn').hidden=!measurementPoints.length;$('measureStatus').textContent=points.length===2?`Đường thẳng: ${distanceText(M.distanceMeters(...measurementPoints))}`:measurementMode?points.length?'Chọn điểm thứ hai.':'Chọn hai điểm trên bản đồ.':'';
}
function addMeasurement(point){if(measurementPoints.length===2)measurementPoints=[];measurementPoints.push({x:point.x,y:point.y});drawMeasurements();}
function updateView(){svg.setAttribute('viewBox',`${view.x} ${view.y} ${view.width} ${view.height}`);const scale=view.width/Math.max(1,svg.clientWidth);if(calibration&&scale!==lastMarkerScale)drawMarkers();}
function fitBounds(x,y,width,height,padding=1.2){const ratio=Math.max(svg.clientWidth,1)/Math.max(svg.clientHeight,1);let w=Math.max(90,width)*padding,h=Math.max(90,height)*padding;if(w/h<ratio)w=h*ratio;else h=w/ratio;view={x:x+width/2-w/2,y:y+height/2-h/2,width:w,height:h};updateView();}
function fitMap(){fitBounds(0,0,3900,3908,1.02);}
function focusEntities(){const points=filteredEntities().map(position).filter(Boolean);if(!points.length){fitMap();return;}const xs=points.map(p=>p.x),ys=points.map(p=>p.y);fitBounds(Math.min(...xs),Math.min(...ys),Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys),1.45);}
function zoom(factor,cx=view.x+view.width/2,cy=view.y+view.height/2){const w=Math.min(11000,Math.max(25,view.width*factor)),f=w/view.width;view={x:cx-(cx-view.x)*f,y:cy-(cy-view.y)*f,width:w,height:view.height*f};updateView();}
function svgPoint(event){const p=svg.createSVGPoint();p.x=event.clientX;p.y=event.clientY;return p.matrixTransform(svg.getScreenCTM().inverse());}
svg.addEventListener('pointerdown',event=>{if(event.button!==0||event.target.closest('.marker'))return;suppressMapClick=false;drag={x:event.clientX,y:event.clientY,vx:view.x,vy:view.y,moved:false};svg.setPointerCapture(event.pointerId);svg.classList.add('dragging');});
svg.addEventListener('pointermove',event=>{if(drag){const factor=view.width/svg.clientWidth;drag.moved ||=Math.hypot(event.clientX-drag.x,event.clientY-drag.y)>3;view.x=drag.vx-(event.clientX-drag.x)*factor;view.y=drag.vy-(event.clientY-drag.y)*factor;updateView();}if(calibration){const world=GatewayProjection.pixelToWorld(svgPoint(event),calibration);$('cursorCoord').textContent=`X ${number(world.x)} / Y ${number(world.y)}`;}});
for(const name of['pointerup','pointercancel','lostpointercapture'])svg.addEventListener(name,()=>{if(drag)suppressMapClick=drag.moved;drag=null;svg.classList.remove('dragging');});
svg.addEventListener('click',event=>{if(measurementMode&&!suppressMapClick&&!event.target.closest('.marker'))addMeasurement(GatewayProjection.pixelToWorld(svgPoint(event),calibration));suppressMapClick=false;});
svg.addEventListener('wheel',event=>{event.preventDefault();const p=svgPoint(event);zoom(event.deltaY>0?1.18:1/1.18,p.x,p.y);},{passive:false});
svg.addEventListener('dblclick',event=>{if(measurementMode||event.target.closest('.marker'))return;const p=svgPoint(event);zoom(.6,p.x,p.y);});
$('zoomIn').onclick=()=>zoom(.7);$('zoomOut').onclick=()=>zoom(1/.7);$('fitBtn').onclick=fitMap;$('focusBtn').onclick=focusEntities;
let previousMapWidth=0;
new ResizeObserver(()=>{const width=svg.clientWidth;if(!initializedMap)fitMap();else{const cx=view.x+view.width/2,cy=view.y+view.height/2,ratio=width/Math.max(svg.clientHeight,1);if(previousMapWidth>0)view.width*=width/previousMapWidth;view.height=view.width/ratio;view.x=cx-view.width/2;view.y=cy-view.height/2;updateView();}previousMapWidth=width;}).observe($('mapContainer'));
function renderHistory(){
  const items=state?.history||[],signature=items.map(x=>x.id).join(',')+'|'+archiveId,select=$('snapshotSelect');if(select.dataset.signature===signature)return;select.dataset.signature=signature;select.replaceChildren();const auto=element('option','','Mới nhất · tự cập nhật');auto.value='';select.append(auto);
  for(const item of items){const time=new Date(item.copied_at),option=element('option','',`${item.filename} · ${vnDate.format(time)} ${vnTime.format(time)} · ${clock(item.duration_ms/1000)}`);option.value=item.id;select.append(option);}if(archiveId&&!items.some(item=>item.id===archiveId)){const old=element('option','','Bản lịch sử đang xem');old.value=archiveId;select.append(old);}select.value=archiveId;
}
function updateSpeciesOptions(){const select=$('speciesFilter'),previous=select.value;select.replaceChildren();const all=element('option','','Tất cả loài');all.value='';select.append(all);for(const species of[...new Set((viewReplay?.entities||[]).map(e=>e.species))].sort()){const option=element('option','',speciesName({species}));option.value=species;select.append(option);}if([...select.options].some(o=>o.value===previous))select.value=previous;const candidates=$('profileCandidates');candidates.replaceChildren();const players=new Map((viewReplay?.entities||[]).filter(e=>e.kind==='player'&&e.steam_id).map(e=>[e.steam_id,e]));for(const e of players.values()){const option=element('option','',`${e.name||e.steam_id} · ${speciesName(e)}`);option.value=e.steam_id;candidates.append(option);}}
async function loadReplay(id){
  if(!id||loadingReplayId===id)return;const token=++loadToken;loadingReplayId=id;$('timelineResolution').textContent='Đang đọc lịch sử…';
  try{const response=await fetch(`/api/replays/${encodeURIComponent(id)}`);if(!response.ok){const error=await response.json();throw Error(error.error||'Không đọc được bản sao.');}const replay=await response.json();if(token!==loadToken)return;
    const changedRecording=viewReplay&&viewReplay.recorded_at!==replay.recorded_at;viewReplay=replay;frameCacheKey='';if(changedRecording&&selectedIdentity){const match=M.followTarget(M.frameEntities(replay,viewTime??replay.time_seconds),selectedIdentity);selected=match?.id??null;}if(viewTime!==null)viewTime=Math.min(viewTime,replay.time_seconds);updateSpeciesOptions();renderFrame();renderStatus();if(!initializedMap){focusEntities();initializedMap=true;}applyFollow();
  }catch(error){if(token===loadToken)toast(error.message);}finally{if(token===loadToken)loadingReplayId=null;}
}
function renderFrame(){
  const r=viewReplay;$('mapEmpty').hidden=!!r;if(!r){$('mapEmpty').textContent=state?.status.error||'Đang đọc bản ghi đầu tiên…';return;}
  const active=allEntities().filter(e=>e.in_scope&&!e.dead&&position(e)),pc=active.filter(e=>e.kind==='player').length,ac=active.filter(e=>e.kind==='ai').length;$('playerCount').textContent=pc;$('aiCount').textContent=ac;$('playerChip').textContent=pc;$('aiChip').textContent=ac;
  $('duration').textContent=clock(r.duration_ms/1000);$('replayName').textContent=`${r.filename} · ${(r.source_size/1048576).toFixed(1)} MiB`;const copied=new Date(r.copied_at);$('updatedTime').textContent=vnTime.format(copied);$('updatedTime').title=vnDate.format(copied);
  const t=currentTime();$('frameTime').textContent=`${viewTime===null?'Cuối bản ghi':'Xem lại'} · ${clock(t)}`;$('timeline').max=String(r.time_seconds);$('timeline').value=String(t);$('timeline').disabled=!r.tracks;$('playBtn').disabled=!r.tracks;$('timelineTime').textContent=clock(t);$('timelineEnd').textContent=clock(r.time_seconds);$('playBtn').textContent=playing?'Ⅱ':'▶';
  $('timelineResolution').textContent=r.tracks?`Bước thời gian ~${r.history_sample_seconds||1}s`:'Chưa có lịch sử trong bản sao này';$('snapshotBadge').textContent=archiveId?'LỊCH SỬ':'MỚI NHẤT';$('snapshotBadge').classList.toggle('archived',!!archiveId);$('exportCsv').disabled=false;$('exportJson').disabled=false;$('meBtn').disabled=!playerProfile?.steam_id;renderEntities();
}
function setTime(time){viewTime=time;frameCacheKey='';renderFrame();applyFollow();}
$('aiDensityToggle').checked=aiDensitySettings.enabled;$('aiDensitySize').value=String(aiDensitySettings.cellMeters);
$('aiDensityToggle').onchange=()=>{aiDensitySettings.enabled=$('aiDensityToggle').checked;saveAiDensitySettings();drawAiDensity();};
$('aiDensitySize').onchange=()=>{aiDensitySettings.cellMeters=Number($('aiDensitySize').value);aiDensitySelected=null;saveAiDensitySettings();renderAiDensity();drawAiDensity();};
$('aiDensitySpecies').onchange=()=>{aiDensitySettings.species=$('aiDensitySpecies').value;aiDensitySelected=null;saveAiDensitySettings();renderAiDensity();drawAiDensity();};
$('aiDensityFit').onclick=()=>focusAiDensity();$('aiDensityMore').onclick=()=>{aiDensityExpanded=!aiDensityExpanded;renderAiDensity();};
for(const [id,key]of[['proximityEnabled','enabled'],['proximityArrows','arrows'],['proximitySound','sound'],['ignoreFriends','ignoreFriends']]){$(id).checked=proximitySettings[key];$(id).onchange=()=>{proximitySettings[key]=$(id).checked;if(key==='enabled')alertJournal.tracking.levels={};if(key==='sound')prepareProximityAudio();saveProximitySettings();};}
$('proximityRadius').value=proximitySettings.radius;$('proximityKind').value=proximitySettings.kind;
function saveProximitySettings(){try{localStorage.setItem('isle-proximity',JSON.stringify(proximitySettings));}catch(_){}proximityCacheKey='';renderEntities();}
$('proximityRadius').onchange=()=>{const value=Number($('proximityRadius').value);proximitySettings.radius=Number.isFinite(value)&&value>0?Math.min(5000,Math.max(10,value)):500;$('proximityRadius').value=proximitySettings.radius;saveProximitySettings();};
$('proximityKind').onchange=()=>{proximitySettings.kind=$('proximityKind').value;saveProximitySettings();};
$('nearbyFocusBtn').onclick=()=>{const report=currentProximity(),p=report.owner&&position(report.owner);if(!report.available||!p)return;const edge=GatewayProjection.worldToPixel({x:report.owner.x+report.radius*100,y:report.owner.y+report.radius*100},calibration),dx=Math.abs(edge.x-p.x),dy=Math.abs(edge.y-p.y);fitBounds(p.x-dx,p.y-dy,dx*2,dy*2,1.3);};
document.addEventListener('pointerdown',prepareProximityAudio,{once:true});document.addEventListener('keydown',prepareProximityAudio,{once:true});
$('profileForm').onsubmit=event=>{event.preventDefault();chooseProfile($('profileSteam').value,$('profileName').value);};
$('profileClear').onclick=()=>chooseProfile('');
$('teammateForm').onsubmit=event=>{event.preventDefault();if(saveTeammate($('teammateSteam').value,$('teammateName').value))$('teammateForm').reset();};
$('clearAlertLog').onclick=()=>{alertJournal.entries=[];persistAlertJournal();renderAlertLog();};renderTeammates();renderAlertLog();
function startFollow(e){saveFollow({steam_id:e.steam_id||null,entity_id:e.id,name:displayName(e)});applyFollow();drawMarkers();toast(`Đang theo dõi ${displayName(e)}.`);}
$('followBtn').onclick=()=>{const e=selectedEntity();if(e)startFollow(e);};$('stopFollowBtn').onclick=()=>{saveFollow(null);drawMarkers();};
$('meBtn').onclick=()=>{const me=playerProfile?.steam_id?M.followTarget(allEntities(),{steam_id:playerProfile.steam_id}):null;if(!me){toast('Chưa thấy tài khoản của bro ở thời điểm này trong replay.');return;}if(!me.in_scope||me.dead)$('historyToggle').checked=true;selectEntity(me.id);if(!me.in_scope)toast(`Đây là vị trí thấy lần cuối của bạn ở ${clock(me.last_seen)}.`);};
$('measureBtn').onclick=()=>{measurementMode=!measurementMode;$('measureBtn').setAttribute('aria-pressed',String(measurementMode));$('mapContainer').classList.toggle('measuring',measurementMode);drawMeasurements();};$('clearMeasureBtn').onclick=()=>{measurementPoints=[];drawMeasurements();};
$('trailToggle').onchange=()=>{drawMarkers();drawDetails();};$('trailWindow').onchange=()=>{drawMarkers();drawDetails();};
$('timeline').oninput=()=>{playing=false;setTime(Number($('timeline').value));};$('jumpEndBtn').onclick=()=>{playing=false;setTime(null);};
$('playBtn').onclick=()=>{if(!viewReplay?.tracks)return;if(!playing&&currentTime()>=viewReplay.time_seconds-.1)viewTime=0;else if(viewTime===null)viewTime=currentTime();playing=!playing;playbackLast=performance.now();renderFrame();};
setInterval(()=>{if(!playing||!viewReplay)return;const tick=performance.now(),delta=(tick-playbackLast)/1000;playbackLast=tick;const next=Math.min(viewReplay.time_seconds,currentTime()+delta*Number($('playbackSpeed').value));if(next>=viewReplay.time_seconds)playing=false;setTime(next);},250);
$('snapshotSelect').onchange=()=>{archiveId=$('snapshotSelect').value;playing=false;viewTime=null;renderHistory();loadReplay(archiveId||state?.replay?.id);};$('liveSnapshotBtn').onclick=()=>{archiveId='';playing=false;viewTime=null;renderHistory();loadReplay(state?.replay?.id);};
$('playersToggle').onclick=()=>{showPlayers=!showPlayers;$('playersToggle').classList.toggle('active',showPlayers);$('playersToggle').setAttribute('aria-pressed',String(showPlayers));renderEntities();};$('aiToggle').onclick=()=>{showAI=!showAI;$('aiToggle').classList.toggle('active',showAI);$('aiToggle').setAttribute('aria-pressed',String(showAI));renderEntities();};
for(const id of['search','growthMin','growthMax'])$(id).addEventListener('input',renderEntities);for(const id of['historyToggle','speciesFilter'])$(id).addEventListener('change',renderEntities);
$('statusFilter').onchange=()=>{if(['lost','dead'].includes($('statusFilter').value))$('historyToggle').checked=true;renderEntities();};
$('resetFilters').onclick=()=>{$('search').value='';$('speciesFilter').value='';$('statusFilter').value='all';$('growthMin').value='0';$('growthMax').value='100';$('historyToggle').checked=false;showPlayers=showAI=true;for(const id of['playersToggle','aiToggle']){$(id).classList.add('active');$(id).setAttribute('aria-pressed','true');}renderEntities();};
function download(content,type,extension){const name=`${(viewReplay.filename||'replay').replace(/[^\w.-]/g,'_').replace(/\.replay$/i,'')}-${Math.floor(currentTime())}s.${extension}`,url=URL.createObjectURL(new Blob([content],{type})),link=element('a');link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('exportCsv').onclick=()=>{if(viewReplay)download(M.csv(filteredEntities(),currentTime()),'text/csv;charset=utf-8','csv');};$('exportJson').onclick=()=>{if(viewReplay)download(JSON.stringify({...viewReplay,view_time_seconds:currentTime(),visible_entities:filteredEntities(),measurement:measurementPoints},null,2),'application/json;charset=utf-8','json');};
async function post(path,body={}){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Isle-Client':'1'},body:JSON.stringify(body)}),result=await response.json();if(!response.ok)throw Error(result.error||'Yêu cầu chưa thành công.');return result;}
$('syncBtn').onclick=async()=>{try{await post('/api/sync');toast('Đã yêu cầu đồng bộ replay.');setTimeout(refresh,300);}catch(error){toast(error.message);}};
function renderStatus(){
  if(!state)return;const s=state.status,busy=['copying','decoding'].includes(s.phase);$('statusLight').className=`status-light${offline||s.phase==='error'?' error':busy?' busy':''}`;$('syncState').textContent=offline?'Mất kết nối service':busy?s.phase==='copying'?'Đang sao chép replay':'Đang đọc vị trí':s.phase==='error'?'Chưa đồng bộ được':'Service đang theo dõi';$('syncBtn').disabled=busy;$('syncIcon').textContent=busy?'…':'↻';
  const left=s.next_sync_at?Math.max(0,Math.ceil((new Date(s.next_sync_at)-Date.now())/1000)):null;$('nextSync').textContent=busy?'Cập nhật bản đồ sau khi giải mã':left!==null?`Đồng bộ tiếp sau ${clock(left)}`:'Tự đồng bộ mỗi 3 phút';$('sourcePath').textContent=state.source_dir+(state.selected_file?' / '+state.selected_file:'');$('copyPath').textContent=state.copy_dir?'Qu?t b?n sao t?i: '+state.copy_dir:'';document.querySelector('.interval-badge').textContent=`${state.interval_seconds}s / lần`;
  const warnings=[];if(offline)warnings.push('Service chưa phản hồi. Kiểm tra service đang chạy.');if(s.error)warnings.push(s.error);const r=viewReplay;
  if(r){if(archiveId)$('sourceAge').textContent=`Bản lưu ngày ${vnDate.format(new Date(r.copied_at))}`;else{const file=state.files.find(f=>f.name===r.filename);if(file){const age=Math.max(0,(Date.now()-new Date(file.modified_at))/1000);$('sourceAge').textContent=age>3600?`File nguồn đã ${Math.floor(age/3600)} giờ chưa đổi`:age>60?`File nguồn đã ${Math.floor(age/60)} phút chưa đổi`:'File nguồn vừa cập nhật';if(age>600)warnings.push('Replay nguồn hiện là bản ghi cũ. Web sẽ cập nhật khi The Isle ghi thêm dữ liệu.');}}if(r.has_partial_tail)warnings.push('Đã lấy các khối hoàn chỉnh; phần đang ghi dở sẽ được đọc ở lần tiếp theo.');}
  $('notice').hidden=!warnings.length;$('notice').textContent=warnings.join(' ');renderHistory();if(viewReplay)renderProximity();
}
async function refresh(){
  const profileToken=profileRequestToken;try{const response=await fetch('/api/state',{signal:AbortSignal.timeout(5000)});if(!response.ok)throw Error('Không kết nối được service');const next=await response.json();if(loadedUIRevision&&next.ui_revision&&next.ui_revision!==loadedUIRevision){window.location.reload();return;}state=next;offline=false;if(profileToken===profileRequestToken)applyProfile(next.player_profile);renderStatus();if(!archiveId&&state.replay?.id!==viewReplay?.id)await loadReplay(state.replay?.id);else if(!viewReplay)renderFrame();}
  catch(error){offline=true;if(state)renderStatus();else{$('syncState').textContent='Chưa kết nối được service';$('statusLight').className='status-light error';$('mapEmpty').textContent='Service chưa phản hồi. Hãy chạy start.cmd.';}}
}
$('settingsBtn').onclick=()=>{$('sourceInput').value=state?.source_dir||'';$('copyInput').value=state?.copy_dir||'';$('fileSelect').replaceChildren();const auto=element('option','','Tự động chọn file mới nhất');auto.value='';$('fileSelect').append(auto);for(const file of state?.files||[]){const option=element('option','',`${file.name} · ${(file.bytes/1048576).toFixed(1)} MiB`);option.value=file.name;$('fileSelect').append(option);}$('fileSelect').value=state?.selected_file||'';$('settingsError').textContent='';$('settingsDialog').showModal();};
$('sourceInput').addEventListener('change',async()=>{const directory=$('sourceInput').value;try{const response=await fetch('/api/source-files?source_dir='+encodeURIComponent(directory)),data=await response.json();if(directory!==$('sourceInput').value)return;if(!response.ok)throw Error(data.error);const select=$('fileSelect');select.replaceChildren();const auto=element('option','','Tự động chọn file mới nhất');auto.value='';select.append(auto);for(const file of data.files){const option=element('option','',file.name);option.value=file.name;select.append(option);}if(data.files.some(f=>f.name==='demo.replay'))select.value='demo.replay';$('settingsError').textContent='';}catch(error){$('settingsError').textContent=error.message;}});
$('settingsForm').onsubmit=async event=>{event.preventDefault();try{await post('/api/config',{source_dir:$('sourceInput').value,filename:$('fileSelect').value,copy_dir:$('copyInput').value});$('settingsDialog').close();toast('Đã lưu nguồn replay.');setTimeout(refresh,300);}catch(error){$('settingsError').textContent=error.message;}};
for(const button of document.querySelectorAll('[data-close]'))button.onclick=()=>$(button.dataset.close).close();
$('detailsBtn').onclick=()=>{const panel=$('replayDetails');panel.replaceChildren();const r=viewReplay;if(!r)panel.append(element('p','','Chưa có bản ghi được xử lý.'));else{detailPairs(panel,[['File',r.filename],['Bản đồ',r.map],['Thời lượng',`${(r.duration_ms/1000).toFixed(3)} giây`],['Ghi lúc (không kèm múi giờ)',r.recorded_at.replace('T',' ')],['Tổng actor từng thấy',r.entities.length],['Frame đã đọc',number(r.diagnostics.frames)],['Cập nhật vị trí',number(r.diagnostics.movements)],['Movement lỗi',number(r.diagnostics.failed_movements)],['Khối / Checkpoint',`${r.chunks.data} / ${r.chunks.checkpoint}`],['Bước lịch sử',r.history_sample_seconds?`${r.history_sample_seconds} giây`:'Chưa có']]);panel.append(element('p','','Chỉ hiển thị đối tượng có trong replay. Timeline dùng vị trí đã ghi gần nhất ở hoặc trước thời điểm chọn; hành trình ngắt khi đối tượng rời phạm vi. Điểm xám là vị trí thấy lần cuối.'));if(r.diagnostics.warnings)panel.append(element('p','',`${r.diagnostics.warnings} thông báo từ bộ đọc:`),element('pre','',r.diagnostics.samples.join('\n')));}$('detailsDialog').showModal();};
(async()=>{try{const[response,profile]=await Promise.all([fetch('/assets/gateway-calibration.json'),fetch('/api/profile')]);if(!response.ok)throw Error('Không đọc được cấu hình Gateway.');calibration=await response.json();if(profile.ok)applyProfile(await profile.json());await refresh();setInterval(refresh,5000);setInterval(renderStatus,1000);}catch(error){$('mapEmpty').textContent=error.message;}})();
