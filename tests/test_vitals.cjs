'use strict';
const assert=require('node:assert/strict');
const m=require('../web/replay-model.js');
const creature={id:1,kind:'player',class_path:'/Game/TheIsle/Core/Characters/Dinosaurs/Example/BP_Example.BP_Example_C',health:125,max_health:500,health_seen:20,max_health_seen:10};
let v=m.dinoVitals(creature);
assert.equal(v.health,125);assert.equal(v.maxHealth,500);assert.equal(v.percent,25);
assert.equal(v.estimatedWeightKg,500,'Weight is explicitly derived, not a separate observed quantity');
assert.equal(m.dinoVitals({...creature,class_path:'/Game/TheIsle/Core/Characters/Animals/Boar/BP_Boar'}).estimatedWeightKg,null,'Do not claim animal mass equals HP');
assert.equal(m.dinoVitals({...creature,class_path:undefined}).estimatedWeightKg,null);
assert.equal(m.dinoVitals({...creature,health:0}).percent,0,'Zero HP is observed data, not missing');
assert.equal(m.dinoVitals({...creature,health:null}).percent,null);
for(const value of [undefined,null,-1,NaN,Infinity,'125'])assert.equal(m.dinoVitals({...creature,health:value}).health,null);
for(const value of [undefined,null,-1,0,NaN,Infinity,'500']){
  v=m.dinoVitals({...creature,max_health:value});assert.equal(v.maxHealth,null);assert.equal(v.percent,null);assert.equal(v.estimatedWeightKg,null);
}
const replay={entities:[{...creature,health:0,max_health:800}],tracks:{1:[
  [0,100,200,300,1,0,.1,0,null,null,null,null],
  [5,100,200,300,1,0,.1,5,100,500,5,5],
  [10,100,200,300,1,0,.1,10,25,500,10,5],
  [20,100,200,300,1,1,.1,20,0,800,20,20]
]}};
assert.equal(m.dinoVitals(m.frameEntities(replay,0)[0]).health,null,'Latest HP cannot leak before first observation');
v=m.dinoVitals(m.frameEntities(replay,7)[0]);assert.equal(v.health,100);assert.equal(v.maxHealth,500);assert.equal(v.healthSeen,5);
assert.equal(m.dinoVitals(m.frameEntities(replay,15)[0]).percent,5,'Seek to damage at the correct time');
assert.equal(m.dinoVitals(m.frameEntities(replay,20)[0]).health,0);
const legacy={entities:[creature],tracks:{1:[[0,100,200,300,1,0,.1,0]]}};
v=m.dinoVitals(m.frameEntities(legacy,0)[0]);assert.equal(v.health,null);assert.equal(v.estimatedWeightKg,null,'Old histories must never borrow final entity vitals');
assert.equal(m.dinoVitals(m.frameEntities({entities:[creature]},0)[0]).health,125,'A snapshot without a timeline may use its own observed values');
const csv=m.csv([creature],20);
assert.ok(csv.includes('"health_hp","max_health_hp","health_percent","estimated_weight_kg_from_max_health"'));
assert.ok(csv.includes('"125","500","25","500","20","10"'));
console.log('PASS: measured HP, missing/zero/invalid data, explicitly estimated dinosaur weight, legacy histories, timeline isolation and CSV units');

const runner={...creature,stamina:120,max_stamina:600,stamina_seen:10,max_stamina_seen:5};
v=m.dinoVitals(runner);assert.equal(v.staminaPercent,20);assert.equal(v.staminaSeen,10);
assert.equal(m.dinoVitals({...runner,stamina:0}).staminaPercent,0,'Exhaustion is an observed zero');
for(const value of [undefined,null,-1,NaN,Infinity,'120']){
  v=m.dinoVitals({...runner,stamina:value});assert.equal(v.stamina,null);assert.equal(v.staminaPercent,null);
}
for(const value of [undefined,null,-1,0,NaN,Infinity,'600']){
  v=m.dinoVitals({...runner,max_stamina:value});assert.equal(v.maxStamina,null);assert.equal(v.staminaPercent,null,'No assumed stamina maximum');
}
const staminaReplay={entities:[{...runner,stamina:0}],tracks:{1:[
  [0,100,200,300,1,0,.1,0,125,500,0,0,null,null,null,null],
  [5,100,200,300,1,0,.1,5,125,500,0,0,300,600,5,5],
  [10,100,200,300,1,0,.1,10,125,500,0,0,120,600,10,5],
  [20,100,200,300,1,0,.1,20,125,500,0,0,0,600,20,5]
]}};
v=m.dinoVitals(m.frameEntities(staminaReplay,0)[0]);assert.equal(v.stamina,null);assert.equal(v.maxStamina,null);
v=m.dinoVitals(m.frameEntities(staminaReplay,7)[0]);assert.equal(v.staminaPercent,50);assert.equal(v.staminaSeen,5);
assert.equal(m.dinoVitals(m.frameEntities(staminaReplay,15)[0]).staminaPercent,20);
assert.equal(m.dinoVitals(m.frameEntities(staminaReplay,20)[0]).staminaPercent,0);
for(const length of [8,12]){
 const old={entities:[runner],tracks:{1:[staminaReplay.tracks[1][1].slice(0,length)]}};
 assert.equal(m.dinoVitals(m.frameEntities(old,7)[0]).stamina,null,'Schema 1/2 tracks cannot borrow final stamina');
}
assert.equal(m.dinoVitals(m.frameEntities({entities:[runner]},0)[0]).stamina,120);
const staminaCsv=m.csv([runner],20);
assert.ok(staminaCsv.includes('"stamina","max_stamina","stamina_percent","stamina_observed_at_seconds","max_stamina_observed_at_seconds"'));
assert.ok(staminaCsv.includes('"120","600","20","10","5"'));
console.log('PASS: stamina percentage, exhaustion, missing/invalid maximum, timeline isolation, schema 1/2 compatibility and CSV');
