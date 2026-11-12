(function (root) {
  'use strict';
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
    if (!replay.tracks) return replay.entities || [];
    const result = [];
    for (const entity of replay.entities || []) {
      const samples = replay.tracks[entity.id];
      if (!samples?.length) continue;
      const index = sampleIndex(samples, time);
      if (index < 0) continue;
      const s = samples[index];
      result.push({...entity, x:s[1], y:s[2], z:s[3], in_scope:s[4] === 1,
        dead:s[5] === -1 ? null : s[5] === 1, growth:s[6], last_seen:s[7]});
    }
    return result;
  }
  function hasPosition(e) {
    return Number.isFinite(e.x) && Number.isFinite(e.y) && !(e.x === 0 && e.y === 0 && e.z === 0);
  }
  function distanceMeters(a, b) { return Math.hypot(a.x - b.x, a.y - b.y) / 100; }
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
    const targets = [...byIdentity.values()].map(entity => ({entity, friendly:entity.kind === 'player' && friends.has(entity.steam_id), ...relativePosition(owner, entity)}))
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
    const columns = ['time_seconds','actor_id','name','steam_id','kind','species','x_cm','y_cm','z_cm','growth_percent','in_scope','dead','last_seen_seconds'];
    const cell = value => {
      if (value === null || value === undefined) return '""';
      let text = String(value);
      if (typeof value === 'string' && /^[=+\-@\t\r]/.test(text)) text = "'" + text;
      return '"' + text.replaceAll('"','""') + '"';
    };
    const rows = entities.map(e => [time,e.id,e.name,e.steam_id,e.kind,e.species,e.x,e.y,e.z,
      e.growth === null ? null : Math.round(e.growth * 10000) / 100,e.in_scope,e.dead,e.last_seen]);
    return '\uFEFF' + [columns, ...rows].map(row => row.map(cell).join(',')).join('\r\n');
  }
  const api = Object.freeze({sampleIndex, frameEntities, hasPosition, distanceMeters, relativePosition, proximity, proximityLevel, targetIdentity, proximityTransitions, routeSegments, routeDistance, matchesFilters, followTarget, csv});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ReplayModel = api;
})(globalThis);
