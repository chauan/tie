'use strict';
const assert=require('node:assert/strict');
const M=require('../web/replay-model.js');
const native=require('./negative-effects-layout.json');

for(let mask=0;mask<=255;mask++){
  const state=M.creatureState({negative_effects_mask:mask,effects_seen:0});
  const expected=native.members.filter(field=>mask&field.mask);
  assert.deepEqual(state.effects,expected.map(field=>field.slot));
  assert.deepEqual(state.effectDetails.map(effect=>effect.key),expected.map(field=>field.native_name));
  assert.equal(state.effectsStatus,mask?'active':'clear');
  assert.equal(state.effectsSeen,0,'The first replay instant is a valid observation');
  assert.ok(!state.effectsLabel.includes('chưa xác định tên'));
}
for(const value of [null,undefined,-1,256,1.5,NaN,Infinity,'128',{},true]){
  const state=M.creatureState({negative_effects_mask:value});
  assert.equal(state.effects,null);
  assert.equal(state.effectDetails,null);
  assert.equal(state.effectsStatus,'unknown');
}
assert.equal(M.creatureState({negative_effects_mask:128}).effectDetails[0].label,'Gãy chân');
assert.equal(M.creatureState({negative_effects_mask:2}).effectDetails[0].label,'Thiếu dịch cơ thể');
assert.equal(M.creatureState({negative_effects_mask:8}).effectDetails[0].label,'Xương giòn');
for(const value of [null,-1,'5',NaN])assert.equal(M.creatureState({effects_seen:value}).effectsSeen,null);

const entity={id:1,species:'Carnotaurus',negative_effects_mask:255,effects_seen:20};
const row=(time,mask,seen)=>[time,100,200,0,1,0,.5,time,...Array(32).fill(null),mask,seen];
const replay={entities:[entity],tracks:{1:[row(0,null,null),row(5,128,5),row(10,0,10),row(20,2,20)]}};
const stateAt=time=>M.creatureState(M.frameEntities(replay,time)[0]);
assert.equal(stateAt(0).effectsStatus,'unknown','Do not borrow final effects before they were observed');
assert.equal(stateAt(7).effectDetails[0].label,'Gãy chân');
assert.equal(stateAt(7).effectsSeen,5);
assert.equal(stateAt(12).effectsStatus,'clear','A later clear mask removes earlier effects');
assert.equal(stateAt(25).effectDetails[0].label,'Thiếu dịch cơ thể');
assert.equal(stateAt(7).effectDetails.length,1,'Rewinding cannot retain later effects');
const legacy={entities:[entity],tracks:{1:[row(0,255,0).slice(0,16)]}};
assert.equal(M.creatureState(M.frameEntities(legacy,20)[0]).effectsStatus,'unknown');
const exported=M.csv(M.frameEntities(replay,7),7);
assert.ok(exported.includes('"negative_effects_status","negative_effects_names"'));
assert.ok(exported.includes('"active","Gãy chân"'));
assert.ok(M.csv(M.frameEntities(replay,12),12).includes('"clear",""'));
assert.ok(M.csv(M.frameEntities(legacy,20),20).includes('"unknown",""'));
console.log('PASS: all 256 effect masks match native metadata; invalid/missing/clear states, timeline isolation, observations and named CSV');
