'use strict';
const assert = require('node:assert/strict');
const m = require(process.argv[2] || '../web/replay-model.js');
const steamId = '76561198000000001';
const owner = {id:1,kind:'player',steam_id:steamId,x:100000,y:100000,z:100,in_scope:true,dead:false,last_seen:60};
const actor = (id,dx,dy,extra={}) => ({...owner,id,steam_id:null,kind:'ai',x:owner.x+dx*100,y:owner.y+dy*100,...extra});
for (const [dx,dy,bearing,direction] of [[0,-100,0,'Bắc'],[100,-100,45,'Đông Bắc'],[100,0,90,'Đông'],[100,100,135,'Đông Nam'],[0,100,180,'Nam'],[-100,100,225,'Tây Nam'],[-100,0,270,'Tây'],[-100,-100,315,'Tây Bắc']]) {
  const relative=m.relativePosition(owner,actor(2,dx,dy));
  assert.equal(relative.bearing,bearing);
  assert.equal(relative.direction,direction);
  assert.ok(Math.abs(relative.distance-Math.hypot(dx,dy))<1e-8);
}
assert.equal(m.relativePosition(owner,{...owner}).bearing,null,'No invented heading at the same position');
const entities=[owner,actor(2,300,400),actor(3,500.01,0),actor(4,400,0,{kind:'player',steam_id:'other'}),
  actor(5,10,0,{in_scope:false}),actor(6,10,0,{dead:true}),actor(7,0,0,{x:0,y:0,z:0}),
  actor(8,1,0,{steam_id:steamId}),actor(9,1,0,{kind:'unknown'}),
  actor(10,1,0,{kind:'player',steam_id:'other',last_seen:30})];
let report=m.proximity(entities,steamId,{radius:500,kind:'all'});
assert.equal(report.available,true);
assert.deepEqual(report.nearby.map(t=>t.entity.id),[4,2],'Inclusive 500 m, current scope, alive, correct kinds, player identity deduplicated');
assert.equal(report.targets.length,3);
assert.deepEqual(m.proximity(entities,steamId,{radius:500,kind:'player'}).nearby.map(t=>t.entity.id),[4]);
assert.deepEqual(m.proximity(entities,steamId,{radius:500,kind:'ai'}).nearby.map(t=>t.entity.id),[2]);
assert.equal(m.proximity(entities,steamId,{radius:399}).nearby.length,0);
for (const self of [{...owner,in_scope:false},{...owner,dead:true},{...owner,x:0,y:0,z:0}]) {
  report=m.proximity([self,actor(2,1,0)],steamId);
  assert.equal(report.available,false,'Never alarm from stale/dead/unavailable owner position');
  assert.equal(report.nearby.length,0);
}
assert.equal(m.proximity(entities,null).available,false);
assert.equal(m.proximity(entities,'missing').available,false);
report=m.proximity([{...owner,in_scope:false,last_seen:90},{...owner,id:20,last_seen:60},actor(2,10,0)],steamId);
assert.equal(report.owner.id,20,'Current actor takes precedence over stale old identity');
const replay={entities:[owner,actor(2,400,0)],tracks:{1:[[0,100000,100000,100,1,0,1,0],[30,120000,100000,100,1,0,1,30],[60,120000,100000,100,0,0,1,60]],2:[[0,140000,100000,100,1,0,1,0]]}};
assert.equal(m.proximity(m.frameEntities(replay,0),steamId).nearby[0].distance,400);
assert.equal(m.proximity(m.frameEntities(replay,30),steamId).nearby[0].distance,200);
assert.equal(m.proximity(m.frameEntities(replay,60),steamId).available,false,'Both positions must belong to the displayed timeline');
for (const [distance,level] of [[0,3],[100,3],[100.01,2],[250,2],[250.01,1],[500,1],[500.01,0],[-1,0],[NaN,0]]) assert.equal(m.proximityLevel(distance),level);
assert.equal(m.proximityLevel(80,50),0,'Never alert outside the configured radius');
assert.equal(m.proximityLevel(30,50),3);
report=m.proximity(entities,steamId,{friendIds:['other'],ignoreFriends:true});
assert.equal(report.nearby.length,2,'Keep teammates visible with distances');
assert.equal(report.nearby.find(t=>t.entity.id===4).friendly,true);
assert.deepEqual(report.alerts.map(t=>t.entity.id),[2],'Mute a teammate by SteamID, even after actor changes');
assert.equal(m.proximity(entities,steamId,{friendIds:['other'],ignoreFriends:false}).alerts.length,2);
const near = distance => [{entity:actor(99,distance,0,{kind:'player',steam_id:'same-player'}),distance}];
let transition=m.proximityTransitions({},near(500));
assert.equal(transition.events[0].level,1);
assert.equal(transition.events[0].type,'enter');
transition=m.proximityTransitions(transition.next,near(250));
assert.equal(transition.events[0].level,2);
assert.equal(transition.events[0].type,'closer');
transition=m.proximityTransitions(transition.next,near(100));
assert.equal(transition.events[0].level,3);
transition=m.proximityTransitions(transition.next,near(150));
assert.equal(transition.events.length,0);
transition=m.proximityTransitions(transition.next,near(99));
assert.equal(transition.events.length,0,'No repeated tier alert due to boundary jitter');
assert.equal(transition.next['steam:same-player'].min_distance,99);
const restored=JSON.parse(JSON.stringify(transition.next));
assert.equal(m.proximityTransitions(restored,near(99)).events.length,0,'Serialized tracking survives page reload');
transition=m.proximityTransitions(transition.next,[]);
assert.equal(m.proximityTransitions(transition.next,near(99)).events.length,1,'A new encounter can alert again');
console.log('PASS: eight compass bearings, centimeters to meters, inclusive 500 m, identity, scope/death, kind filters, duplicates and timeline-relative distances');
console.log('PASS: 500/250/100 m tiers, teammate visibility/muting, escalation, jitter suppression, closest distance, persisted deduplication and reentry');
