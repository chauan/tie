(function(root){
  'use strict';
  const M=root.ReplayModel;
  const node=(tag,className,text)=>{const e=document.createElement(tag);if(className)e.className=className;if(text!==undefined)e.textContent=text;return e;};
  const num=value=>Number.isFinite(value)?value.toLocaleString('vi-VN',{maximumFractionDigits:1}):'Chưa rõ';
  const clock=value=>Number.isFinite(value)?`${Math.floor(value/60).toString().padStart(2,'0')}:${Math.floor(value%60).toString().padStart(2,'0')}`:'Chưa rõ';
  function icon(name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),use=document.createElementNS('http://www.w3.org/2000/svg','use');svg.setAttribute('class','ui-icon');svg.setAttribute('aria-hidden','true');use.setAttribute('href',`/assets/survival-icons.svg#${name}`);svg.append(use);return svg;}
  function portrait(element,entity){const species=String(entity?.species||'').toLowerCase();element.dataset.portrait=species.includes('carnotaurus')?'carnotaurus':species.includes('allosaurus')?'allosaurus':'unknown';if(!element.firstChild)element.append(icon('skull'));}
  function pairList(rows){const dl=node('dl','target-facts');for(const [label,value]of rows){dl.append(node('dt','',label),node('dd','',value));}return dl;}
  function meter(label,value,maximum,percent,seen,className,unit=''){
    const card=node('div',`vital-card ${className}`);
    card.append(node('div','vital-label',className==='stamina'&&percent!==null?`Stamina · ${num(percent)}%`:label));
    const text=value===null?'Chưa rõ':`${num(value)}${maximum!==null?' / '+num(maximum):''}${unit?' '+unit:''}`;
    card.append(node('strong','vital-value',text));
    if(percent!==null){
      const bar=node('div',`vital-bar entity-${className==='hp'?'health':className}-meter`);
      bar.dataset.level=percent<=25?'low':percent<=50?'medium':'high';bar.setAttribute('role','meter');
      bar.setAttribute('aria-label',`${label} đã ghi trong replay`);bar.setAttribute('aria-valuemin','0');
      bar.setAttribute('aria-valuemax',String(maximum));bar.setAttribute('aria-valuenow',String(Math.min(maximum,value)));
      const fill=node('span');fill.style.width=`${Math.min(100,Math.max(0,percent))}%`;bar.append(fill);card.append(bar);
    }
    card.append(node('span','vital-caption',value===null?'Chưa có trong replay ở mốc này':`${percent!==null?num(percent)+'% · ':''}ghi ${clock(seen)}`));
    return card;
  }
  function measure(label,value,note,symbol){const e=node('div','target-measure');e.append(icon(symbol),node('span','measure-name',label),node('strong','measure-value',value));if(note)e.append(node('span','measure-note',note));return e;}
  function renderEffects(entity,state,time){
    const section=node('section','target-conditions target-effects');section.dataset.state=state.effectsStatus;
    const heading=node('h4','','Hiệu ứng đang dính');heading.prepend(icon('effect-alert'));
    if(state.effects!==null)heading.append(node('span','effect-count',String(state.effects.length)));
    section.append(heading);
    if(state.effectDetails?.length){
      const list=node('ul','effect-list');list.setAttribute('aria-label','Hiệu ứng được ghi nhận');
      for(const effect of state.effectDetails){const item=node('li','effect-card'),text=node('span','effect-copy');item.dataset.effect=effect.key;
        text.append(node('strong','effect-name',effect.label),node('span','effect-native',effect.name));item.append(icon(effect.symbol),text);list.append(item);}
      section.append(list);
    }else section.append(node('p','effect-state',state.effectsLabel));
    if(state.effects!==null){
      const age=state.effectsSeen!==null&&Number.isFinite(time)&&time>=state.effectsSeen?time-state.effectsSeen:null;
      const observed=state.effectsSeen===null?'Chưa rõ mốc ghi nhận':`Ghi nhận ở ${clock(state.effectsSeen)}${age!==null?` · cách mốc đang xem ${clock(age)}`:''}`;
      section.append(node('p','effect-observation',observed));
      if(entity.dead||!entity.in_scope)section.append(node('p','effect-scope','Trạng thái ở lần ghi cuối; dino đã chết hoặc rời phạm vi.'));
    }
    return section;
  }
  function render(container,entity,options={}){
    const opened=new Set([...container.querySelectorAll('details[open]')].map(e=>e.dataset.section));
    container.replaceChildren();container.hidden=false;
    if(!entity){const empty=node('div','empty-inspector');empty.append(node('span','inspector-symbol','◎'),node('h3','','Chọn một dino'),node('p','','Bấm điểm trên bản đồ hoặc tên trong danh sách để xem chỉ số và hành trình đã ghi.'));container.append(empty);return;}
    const e=entity,v=M.dinoVitals(e),state=M.creatureState(e),head=node('div','target-heading');
    const context=node('span','target-context');context.append(icon('activity'),document.createTextNode(options.self?'Dino của bạn':'Dino đang chọn'));head.append(context);
    const identity=node('div','target-identity'),art=node('span','dino-portrait target-portrait'),identityText=node('div','target-identity-text');art.setAttribute('aria-hidden','true');portrait(art,e);
    identityText.append(node('h3','',options.species||e.species||'Chưa rõ loài'),node('p','target-name',options.name||e.name||'Chưa có tên'));
    const chips=node('div','target-chips');
    const status=node('span',`target-chip ${e.dead?'danger':e.in_scope?'active':'muted'}`,e.dead?'Đã chết':e.in_scope?'Trong phạm vi ghi':'Vị trí cuối cùng');chips.append(status);
    if(options.friendly)chips.append(node('span','target-chip friendly',options.sameGroup?'Cùng nhóm trong game':'Đồng đội'));
    if(e.is_group_leader===true)chips.append(node('span','target-chip leader','Trưởng nhóm'));
    identityText.append(chips);identity.append(art,identityText);head.append(identity);container.append(head);
    if(options.relative){const near=node('div','target-relative'),arrow=node('span','target-bearing',options.relative.bearing===null?'•':'↑');if(options.relative.bearing!==null)arrow.style.transform=`rotate(${options.relative.bearing}deg)`;near.append(arrow,node('strong','',options.distanceText||`${num(options.relative.distance)} m`),node('span','',options.relative.direction));container.append(near);}
    const vitals=node('div','target-vitals');
    vitals.append(meter('Máu (HP)',v.health,v.maxHealth,v.percent,v.healthSeen,'hp','HP'),
      meter('Blood',v.blood,v.maxBlood,v.bloodPercent,v.bloodSeen,'blood'),
      meter('Stamina',v.stamina,v.maxStamina,v.staminaPercent,v.staminaSeen,'stamina'));
    container.append(vitals);
    const measures=node('div','target-measures');
    measures.append(measure('Weight ghi nhận',v.weight===null?'Chưa rõ':num(v.weight),'Giá trị đọc trực tiếp; chưa đối chiếu đơn vị kg','weight'),
      measure('Thức ăn',v.foodValue===null?'Chưa rõ':`${num(v.foodValue)}${v.maxFoodValue!==null?' / '+num(v.maxFoodValue):''}`,v.foodPercent!==null?`${num(v.foodPercent)}% chỉ số FoodValue`:'Chưa có đủ dữ liệu thức ăn','food'),
      measure('Vận tốc',v.speedMps===null?'Chưa rõ':`${num(v.speedMps)} m/s`,v.speedMps===null?'Chưa có vector vận tốc':`${num(v.speedMps*3.6)} km/h`,'speed'),
      measure('Hướng quay',v.heading===null?'Chưa rõ':`${num(v.heading)}°`,v.heading===null?'Chưa có hướng quay':'0° Bắc · 90° Đông','heading'));
    container.append(measures);
    container.append(renderEffects(e,state,options.time));
    const conditions=node('section','target-conditions'),conditionTitle=node('h4','','Hành động & trạng thái');conditionTitle.prepend(icon('activity'));conditions.append(conditionTitle,node('p','ability-state',state.abilityLabel));
    conditions.append(pairList([['Nhóm trong game',Number.isInteger(e.group_id)&&e.group_id!==0?`#${e.group_id}`:'Chưa có dữ liệu nhóm'],
      ['Trưởng nhóm',e.is_group_leader===null||e.is_group_leader===undefined?'Chưa rõ':e.is_group_leader?'Có':'Không'],
      ['Trưởng thành',Number.isFinite(e.growth)?`${num(e.growth*100)}%`:'Chưa rõ'],['RottenValue',v.rottenValue===null?'Chưa rõ':num(v.rottenValue)]]));container.append(conditions);
    const details=node('details','target-metadata');details.dataset.section='metadata';details.open=opened.has('metadata');details.append(node('summary','','Tọa độ & dữ liệu chi tiết'));
    const rows=[['SteamID',e.steam_id||'Chưa rõ'],['X / Y (cm)',Number.isFinite(e.x)&&Number.isFinite(e.y)?`${num(e.x)} / ${num(e.y)}`:'Chưa rõ'],['Độ cao Z (cm)',num(e.z)],['Vị trí ghi ở',clock(e.last_seen)],['Weight ghi ở',clock(v.weightSeen)],['Blood ghi ở',clock(v.bloodSeen)],['Thức ăn ghi ở',clock(v.foodSeen)],['Nhóm ghi ở',clock(e.group_seen)],['Hành động ghi ở',clock(e.ability_seen)],['Hiệu ứng ghi ở',clock(e.effects_seen)]];
    if(state.ability!==null)rows.push(['Mã hành động',String(state.ability)]);
    if(state.effects!==null)rows.push(['Hiệu ứng đã ghi',state.effectsLabel]);
    if(v.estimatedWeightKg!==null)rows.push(['Cân nặng ước tính cũ',`~${num(v.estimatedWeightKg)} kg (ước tính từ máu tối đa)`]);
    else rows.push(['Cân nặng ước tính cũ','Chưa có dữ liệu cân nặng']);
    if(options.routeDistance)rows.push(['Đường đã ghi',options.routeDistance]);
    details.append(pairList(rows),node('p','vitals-note','Weight là số đọc trực tiếp. Phép ước tính kg từ HP tối đa chưa được kiểm chứng cho mọi loài hoặc máy chủ.'));container.append(details);
    if(options.actions)container.append(options.actions);
  }
  root.CreaturePanel=Object.freeze({render,portrait,icon});
})(globalThis);
