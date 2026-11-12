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
