(function (root) {
  'use strict';
  const extendedFields=['weight','weight_seen','blood','max_blood','blood_seen','max_blood_seen',
    'food_value','max_food_value','food_seen','max_food_seen','rotten_value','rotten_seen',
    'yaw','pitch','roll','velocity_x','velocity_y','velocity_z','movement_seen',
    'group_id','is_group_leader','group_seen','ability_state','ability_seen','negative_effects_mask','effects_seen'];
  function excludedEntity(entity){return /coalecanth|coalacanth|coelacanth/i.test(`${entity?.class_path||''} ${entity?.species||''}`);}
  function sameGroup(a,b){return Number.isInteger(a?.group_id)&&a.group_id!==0&&Number.isInteger(b?.group_id)&&a.group_id===b.group_id;}
  function sampleIndex(samples, time) {
    let lo = 0, hi = samples.length - 1, answer = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (samples[mid][0] <= time + 0.001) { answer = mid; lo = mid + 1; }
      else hi = mid - 1;
    }
    return answer;
  }
  function frameEntities(replay, time) {
    if (!replay) return [];
    if (!replay.tracks) return (replay.entities || []).filter(e=>!excludedEntity(e));
    const result = [];
    for (const entity of replay.entities || []) {
      if(excludedEntity(entity))continue;
      const samples = replay.tracks[entity.id];
      if (!samples?.length) continue;
      const index = sampleIndex(samples, time);
      if (index < 0) continue;
      const s = samples[index];
      const extended=Object.fromEntries(extendedFields.map((key,i)=>[key,s.length>=42?s[16+i]:null]));
      extended.is_group_leader=extended.is_group_leader===null||extended.is_group_leader===-1?null:extended.is_group_leader===1;
      result.push({...entity,...extended, x:s[1], y:s[2], z:s[3], in_scope:s[4] === 1,
        dead:s[5] === -1 ? null : s[5] === 1, growth:s[6], last_seen:s[7],
        health:s.length>=12?s[8]:null, max_health:s.length>=12?s[9]:null,
        health_seen:s.length>=12?s[10]:null, max_health_seen:s.length>=12?s[11]:null,
        stamina:s.length>=16?s[12]:null, max_stamina:s.length>=16?s[13]:null,
        stamina_seen:s.length>=16?s[14]:null, max_stamina_seen:s.length>=16?s[15]:null});
    }
    return result;
  }
  function hasPosition(e) {
    return Number.isFinite(e.x) && Number.isFinite(e.y) && !(e.x === 0 && e.y === 0 && e.z === 0);
  }
  function distanceMeters(a, b) { return Math.hypot(a.x - b.x, a.y - b.y) / 100; }
  function dinoVitals(entity) {
    const valid = value => Number.isFinite(value) && value >= 0 ? value : null;
    const health = valid(entity?.health), maximum = valid(entity?.max_health);
    const maxHealth = maximum !== null && maximum > 0 ? maximum : null;
    const stamina = valid(entity?.stamina), staminaMaximum = valid(entity?.max_stamina);
    const maxStamina = staminaMaximum !== null && staminaMaximum > 0 ? staminaMaximum : null;
    const dinosaur = typeof entity?.class_path === 'string' && entity.class_path.includes('/Characters/Dinosaurs/');
    const weight=valid(entity?.weight),blood=valid(entity?.blood),bloodMaximum=valid(entity?.max_blood),maxBlood=bloodMaximum>0?bloodMaximum:null;
    const foodValue=valid(entity?.food_value),foodMaximum=valid(entity?.max_food_value),maxFoodValue=foodMaximum>0?foodMaximum:null;
    const motion=[entity?.velocity_x,entity?.velocity_y,entity?.velocity_z].every(Number.isFinite);
    return {health, maxHealth, percent:health!==null&&maxHealth!==null?health/maxHealth*100:null,
      estimatedWeightKg:dinosaur?maxHealth:null, healthSeen:valid(entity?.health_seen), maxHealthSeen:valid(entity?.max_health_seen),
      stamina, maxStamina, staminaPercent:stamina!==null&&maxStamina!==null?stamina/maxStamina*100:null,
      staminaSeen:valid(entity?.stamina_seen), maxStaminaSeen:valid(entity?.max_stamina_seen),
      weight,weightSeen:valid(entity?.weight_seen),blood,maxBlood,bloodPercent:blood!==null&&maxBlood!==null?blood/maxBlood*100:null,
      bloodSeen:valid(entity?.blood_seen),maxBloodSeen:valid(entity?.max_blood_seen),
      foodValue,maxFoodValue,foodPercent:foodValue!==null&&maxFoodValue!==null?foodValue/maxFoodValue*100:null,
      foodSeen:valid(entity?.food_seen),maxFoodSeen:valid(entity?.max_food_seen),rottenValue:valid(entity?.rotten_value),rottenSeen:valid(entity?.rotten_seen),
      speedMps:motion?Math.hypot(entity.velocity_x,entity.velocity_y,entity.velocity_z)/100:null,
      heading:Number.isFinite(entity?.yaw)?((entity.yaw+90)%360+360)%360:null,movementSeen:valid(entity?.movement_seen)};
  }
  const abilityNames={0:'Kéo xác bên trái',1:'Kéo xác bên phải',2:'Giữ vật',3:'Giữ mục tiêu sau cú lao',4:'Giữ mục tiêu',5:'Bắt đầu động tác giữ',10:'Vồ mục tiêu nhỏ',11:'Vồ mục tiêu lớn',18:'Bị vồ (nhỏ)',19:'Bị vồ (lớn)',20:'Vùng vẫy khi bị vồ (nhỏ)',21:'Vùng vẫy khi bị vồ (lớn)',22:'Bị ghì',23:'Bị ghì phía trước',24:'Hồi phục sau khi bị vồ',27:'Bị nuốt',28:'Được mang',29:'Bị kéo',30:'Xác',52:'Bị giữ sau cú lao',53:'Bị kẹp',59:'Phôi',60:'Đang nở',69:'Bị vồ',70:'Vùng vẫy khi bị vồ',84:'Không có hành động đặc biệt'};
  // Native FNegativeEffects property offsets and NetSerialize order: EFFECTS-SOURCES.md.
  const effectDefinitions=Object.freeze([
    {key:'bSlovenly',label:'Vệ sinh kém',name:'Slovenly',symbol:'effect-alert'},
    {key:'bFluidDeficient',label:'Thiếu dịch cơ thể',name:'Fluid Deficient',symbol:'effect-fluid'},
    {key:'bHasCataracts',label:'Đục thủy tinh thể',name:'Cataracts',symbol:'effect-eye'},
    {key:'bGlassBones',label:'Xương giòn',name:'Glass Bones',symbol:'effect-bone'},
    {key:'bIsSickState',label:'Đang bị bệnh',name:'Sick',symbol:'effect-alert'},
    {key:'bIsHeadFractured',label:'Gãy xương đầu',name:'Head Fracture',symbol:'effect-bone'},
    {key:'bIsBodyFractured',label:'Gãy xương thân',name:'Body Fracture',symbol:'effect-bone'},
    {key:'bIsLegsFractured',label:'Gãy chân',name:'Leg Fracture',symbol:'effect-bone'}
  ].map(Object.freeze));
  function creatureState(entity){
    const raw=entity?.ability_state,ability=Number.isInteger(raw)&&raw>=0&&raw<=127?raw:null;
    const mask=entity?.negative_effects_mask,effects=Number.isInteger(mask)&&mask>=0&&mask<=255?Array.from({length:8},(_,i)=>i+1).filter(i=>mask&(1<<(i-1))):null;
    const effectDetails=effects?.map(slot=>effectDefinitions[slot-1])??null;
    const effectsSeen=Number.isFinite(entity?.effects_seen)&&entity.effects_seen>=0?entity.effects_seen:null;
    return {ability,abilityLabel:ability===null?'Chưa rõ':abilityNames[ability]||`Hành động #${ability} (chưa rõ tên)`,effects,effectDetails,effectsSeen,
      effectsStatus:effects===null?'unknown':effects.length?'active':'clear',
      effectsLabel:effects===null?'Chưa có dữ liệu hiệu ứng ở mốc này':effects.length?effectDetails.map(effect=>effect.label).join(' · '):'Không ghi nhận hiệu ứng bất lợi'};
  }
  function aiDensity(entities, options = {}) {
    const cellMeters = [250, 500, 1000].includes(options.cellMeters) ? options.cellMeters : 500;
    const units = cellMeters * 100, bounds = options.bounds || {};
    const bounded = ['world_x_min','world_x_max','world_y_min','world_y_max'].every(k => Number.isFinite(bounds[k])) && bounds.world_x_max > bounds.world_x_min && bounds.world_y_max > bounds.world_y_min;
    const x0 = bounded ? bounds.world_x_min : 0, y0 = bounded ? bounds.world_y_min : 0;
    const actors = new Map(), cells = new Map();
    for (const e of entities || []) {
      if (e.kind !== 'ai' || !e.in_scope || e.dead || !hasPosition(e) || e.id === undefined || e.id === null) continue;
      if (bounded && (e.x < x0 || e.x > bounds.world_x_max || e.y < y0 || e.y > bounds.world_y_max)) continue;
      const key = String(e.id), previous = actors.get(key);
      if (!previous || (e.last_seen ?? 0) > (previous.last_seen ?? 0)) actors.set(key, e);
    }
    let total = 0;
    for (const e of actors.values()) {
      if (options.species && e.species !== options.species) continue;
      let col = Math.floor((e.x - x0) / units), row = Math.floor((e.y - y0) / units);
      if (bounded) {
        col = Math.min(col, Math.ceil((bounds.world_x_max - x0) / units) - 1);
        row = Math.min(row, Math.ceil((bounds.world_y_max - y0) / units) - 1);
      }
      const id = `${cellMeters}:${col}:${row}`;
      if (!cells.has(id)) {
        const xMin = x0 + col * units, yMin = y0 + row * units;
        const xMax = bounded ? Math.min(xMin + units, bounds.world_x_max) : xMin + units;
        const yMax = bounded ? Math.min(yMin + units, bounds.world_y_max) : yMin + units;
        cells.set(id, {id, col, row, x:(xMin+xMax)/2, y:(yMin+yMax)/2, bounds:{xMin,xMax,yMin,yMax}, count:0, species:new Map()});
      }
      const cell = cells.get(id), name = e.species || '';
      cell.count++; total++; cell.species.set(name, (cell.species.get(name) || 0) + 1);
    }
    const ranked = [...cells.values()].map(cell => ({...cell, species:[...cell.species].map(([name,count]) => ({name,count})).sort((a,b) => b.count-a.count || a.name.localeCompare(b.name))}))
      .sort((a,b) => b.count-a.count || a.row-b.row || a.col-b.col);
    return {cellMeters, total, cells:ranked, maxCount:ranked[0]?.count || 0};
  }
  // World X points east and world Y south. Bearings are clockwise from north.
  function relativePosition(origin, target) {
    if (!origin || !target || !hasPosition(origin) || !hasPosition(target)) return null;
    const distance = distanceMeters(origin, target);
    const bearing = distance < 0.001 ? null : (Math.atan2(target.x - origin.x, origin.y - target.y) * 180 / Math.PI + 360) % 360;
    const directions = ['Bắc','Đông Bắc','Đông','Đông Nam','Nam','Tây Nam','Tây','Tây Bắc'];
    return {distance, bearing, direction:bearing === null ? 'Cùng vị trí' : directions[Math.round(bearing / 45) % 8]};
  }
  function proximity(entities, steamId, options = {}) {
    const radius = Number.isFinite(options.radius) && options.radius > 0 ? options.radius : 500;
    const active = e => e.in_scope && !e.dead && hasPosition(e);
    const ownActors = steamId ? entities.filter(e => e.steam_id === steamId) : [];
    const owner = ownActors.filter(active).sort((a,b) => b.last_seen - a.last_seen)[0] || followTarget(ownActors, {steam_id:steamId});
    if (!owner || !active(owner)) return {owner, available:false, targets:[], nearby:[], alerts:[], radius};
    // Prefer one current actor for a player's SteamID after respawn/channel changes.
    const byIdentity = new Map();
    for (const e of entities) {
      if (e.steam_id === steamId || e.id === owner.id || !active(e) || !['player','ai'].includes(e.kind)) continue;
      const key = e.kind === 'player' && e.steam_id ? `steam:${e.steam_id}` : `actor:${e.id}`;
      const previous = byIdentity.get(key);
      if (!previous || e.last_seen > previous.last_seen) byIdentity.set(key, e);
    }
    const friends = new Set(options.friendIds || []);
    const targets = [...byIdentity.values()].map(entity => ({entity, friendly:entity.kind === 'player' && (friends.has(entity.steam_id)||sameGroup(owner,entity)), ...relativePosition(owner, entity)}))
      .sort((a,b) => a.distance - b.distance || a.entity.id - b.entity.id);
    const nearby = targets.filter(t => t.distance <= radius && (!options.kind || options.kind === 'all' || t.entity.kind === options.kind));
    const alerts = nearby.filter(t => !(options.ignoreFriends && t.friendly));
    return {owner, available:true, targets, nearby, alerts, radius};
  }
  function proximityLevel(distance, radius = 500) {
    if (!Number.isFinite(distance) || distance < 0 || distance > radius) return 0;
    return distance <= Math.min(100, radius) ? 3 : distance <= Math.min(250, radius) ? 2 : 1;
  }
  function targetIdentity(e) { return e.kind === 'player' && e.steam_id ? `steam:${e.steam_id}` : `actor:${e.id}`; }
  function proximityTransitions(previous, targets, radius = 500) {
    const next = Object.create(null), events = [];
    for (const target of targets) {
      const key = targetIdentity(target.entity), level = proximityLevel(target.distance, radius);
      if (!level) continue;
      const before = previous[key];
      next[key] = {...before, level:Math.max(level, before?.level || 0), min_distance:Math.min(target.distance, before?.min_distance ?? Infinity)};
      if (!before || level > before.level) events.push({key, target, level, type:before ? 'closer' : 'enter'});
    }
    // Keep the highest level in one encounter; small boundary jitter cannot repeat it.
    events.sort((a,b) => b.level - a.level || a.target.distance - b.target.distance);
    return {next, events};
  }
  function routeSegments(replay, id, time, windowSeconds = Infinity) {
    const samples = replay?.tracks?.[id] || [];
    const start = Math.max(0, time - windowSeconds), end = sampleIndex(samples, time);
    if (end < 0) return [];
    const first = Math.max(0, sampleIndex(samples, start));
    const maxGap = Math.max(15, (replay.history_sample_seconds || 1) * 2.5);
    const segments = [];
    let segment = [], previousTime = null;
    const flush = () => { if (segment.length > 1) segments.push(segment); segment = []; };
    for (let i = first; i <= end; i++) {
      const s = samples[i], point = {t:s[0],x:s[1],y:s[2],z:s[3]};
      if (!s[4] || s[5] === 1 || !hasPosition(point)) { flush(); previousTime = null; continue; }
      if (previousTime !== null && s[0] - previousTime > maxGap) flush();
      previousTime = s[0];
      const last = segment.at(-1);
      if (!last || last.x !== point.x || last.y !== point.y) segment.push(point);
    }
    flush();
    return segments;
  }
  function routeDistance(segments) {
    let distance = 0;
    for (const segment of segments) for (let i = 1; i < segment.length; i++) distance += distanceMeters(segment[i - 1], segment[i]);
    return distance;
  }
  function matchesFilters(entity, filters = {}) {
    if (!filters.history && (!entity.in_scope || entity.dead)) return false;
    if (entity.kind === 'player' && filters.players === false || entity.kind === 'ai' && filters.ai === false) return false;
    if (filters.species && entity.species !== filters.species) return false;
    if (filters.status === 'active' && (!entity.in_scope || entity.dead)) return false;
    if (filters.status === 'dead' && entity.dead !== true) return false;
    if (filters.status === 'lost' && entity.in_scope) return false;
    const min = filters.minGrowth ?? 0, max = filters.maxGrowth ?? 100;
    if ((min > 0 || max < 100) && (entity.growth === null || entity.growth * 100 < min || entity.growth * 100 > max)) return false;
    const query = (filters.query || '').trim().toLocaleLowerCase();
    return !query || `${entity.name || ''} ${entity.species} ${entity.steam_id || ''} ${entity.id}`.toLocaleLowerCase().includes(query);
  }
  function followTarget(entities, key) {
    if (!key) return null;
    return entities.filter(e => key.steam_id ? e.steam_id === key.steam_id : e.id === key.entity_id)
      .sort((a, b) => Number(b.in_scope && !b.dead) - Number(a.in_scope && !a.dead) || b.last_seen - a.last_seen)[0] || null;
  }
  function csv(entities, time) {
    const columns = ['time_seconds','actor_id','name','steam_id','kind','species','x_cm','y_cm','z_cm','growth_percent','in_scope','dead','last_seen_seconds',
      'health_hp','max_health_hp','health_percent','estimated_weight_kg_from_max_health','health_observed_at_seconds','max_health_observed_at_seconds',
      'stamina','max_stamina','stamina_percent','stamina_observed_at_seconds','max_stamina_observed_at_seconds',
      ...extendedFields,'blood_percent','food_percent','speed_mps','heading_degrees','negative_effects_status','negative_effects_names'];
    const cell = value => {
      if (value === null || value === undefined) return '""';
      let text = String(value);
      if (typeof value === 'string' && /^[=+\-@\t\r]/.test(text)) text = "'" + text;
      return '"' + text.replaceAll('"','""') + '"';
    };
    const rows = entities.map(e => { const v=dinoVitals(e),state=creatureState(e); return [time,e.id,e.name,e.steam_id,e.kind,e.species,e.x,e.y,e.z,
      e.growth === null ? null : Math.round(e.growth * 10000) / 100,e.in_scope,e.dead,e.last_seen,
      v.health,v.maxHealth,v.percent,v.estimatedWeightKg,v.healthSeen,v.maxHealthSeen,
      v.stamina,v.maxStamina,v.staminaPercent,v.staminaSeen,v.maxStaminaSeen,
      ...extendedFields.map(key=>e[key]),v.bloodPercent,v.foodPercent,v.speedMps,v.heading,state.effectsStatus,state.effectDetails?.map(effect=>effect.label).join('; ')??null]; });
    return '\uFEFF' + [columns, ...rows].map(row => row.map(cell).join(',')).join('\r\n');
  }
  const api = Object.freeze({sampleIndex, frameEntities, hasPosition, distanceMeters, dinoVitals, creatureState, excludedEntity, sameGroup, aiDensity, relativePosition, proximity, proximityLevel, targetIdentity, proximityTransitions, routeSegments, routeDistance, matchesFilters, followTarget, csv});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ReplayModel = api;
})(globalThis);
