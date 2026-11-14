'use strict';
const assert=require('node:assert/strict');
const m=require('../web/replay-model.js');
const entity={id:1,class_path:'/Game/TheIsle/Core/Characters/Dinosaurs/Example/BP_Example',in_scope:true,x:100,y:200,z:300,
  health:200,max_health:1000,weight:750,weight_seen:10,blood:100,max_blood:400,blood_seen:10,food_value:50,max_food_value:200,
  rotten_value:7,yaw:0,velocity_x:300,velocity_y:400,velocity_z:0,movement_seen:10,group_id:-123,is_group_leader:false,
  ability_state:84,negative_effects_mask:130};
let v=m.dinoVitals(entity);
assert.equal(v.weight,750);assert.equal(v.bloodPercent,25);assert.equal(v.foodPercent,25);assert.equal(v.rottenValue,7);
assert.equal(v.speedMps,5);assert.equal(v.heading,90,'World yaw zero faces east');
assert.equal(m.dinoVitals({...entity,yaw:270}).heading,0,'World yaw 270 faces north');
assert.equal(m.dinoVitals({...entity,velocity_z:undefined}).speedMps,null,'Missing velocity is not stationary');
assert.equal(m.dinoVitals({...entity,velocity_x:0,velocity_y:0}).speedMps,0);
assert.equal(m.dinoVitals({...entity,blood:0}).bloodPercent,0);
assert.equal(m.dinoVitals({...entity,max_blood:0}).bloodPercent,null);
assert.equal(m.dinoVitals({...entity,weight:'750'}).weight,null);
assert.equal(m.sameGroup(entity,{group_id:-123}),true,'Signed group keys can identify matching groups');
for(const key of [null,undefined,0,NaN,'-123'])assert.equal(m.sameGroup({group_id:key},{group_id:key}),false);
assert.equal(m.creatureState(entity).abilityLabel,'Không có hành động đặc biệt');
assert.deepEqual(m.creatureState(entity).effects,[2,8]);
assert.deepEqual(m.creatureState({...entity,negative_effects_mask:0}).effects,[]);
assert.equal(m.creatureState({...entity,negative_effects_mask:256}).effects,null);
assert.ok(m.creatureState({...entity,ability_state:127}).abilityLabel.includes('chưa rõ tên'));
const row=[10,100,200,300,1,0,.5,10,200,1000,10,10,100,200,10,10,
  750,10,100,400,10,10,50,200,10,10,7,10,0,0,0,300,400,0,10,-123,0,10,84,10,130,10];
assert.equal(row.length,42);
const replay={entities:[entity],tracks:{1:[row]}};
let at=m.frameEntities(replay,10)[0];
assert.equal(m.dinoVitals(at).weight,750);assert.equal(at.is_group_leader,false);assert.equal(at.negative_effects_mask,130);
for(const length of [8,12,16]){
  at=m.frameEntities({entities:[entity],tracks:{1:[row.slice(0,length)]}},10)[0];
  assert.equal(at.weight,null);assert.equal(at.blood,null);assert.equal(at.yaw,null);assert.equal(at.group_id,null);
  assert.equal(at.ability_state,null);assert.equal(at.negative_effects_mask,null,'Old timelines cannot borrow final actor states');
}
for(const species of ['Coalecanth','Fish_Coalacanth','Coelacanth']){
 const fish={...entity,id:2,species};
 assert.deepEqual(m.frameEntities({entities:[fish]},10),[]);
 assert.deepEqual(m.frameEntities({entities:[fish],tracks:{2:[row]}},10),[]);
}
assert.equal(m.frameEntities({entities:[{...entity,species:'Fish_RainbowFish'}]},10).length,1);
const report=m.proximity([{...entity,kind:'player',steam_id:'owner',dead:false,last_seen:10},
  {...entity,id:2,kind:'player',steam_id:'other',dead:false,last_seen:10,x:200}], 'owner',{ignoreFriends:true});
assert.equal(report.nearby.length,1);assert.equal(report.nearby[0].friendly,true);assert.equal(report.alerts.length,0);
const csv=m.csv([entity],10);for(const column of ['weight','blood','max_blood','food_value','rotten_value','group_id','speed_mps','ability_state','negative_effects_mask'])assert.ok(csv.includes('"'+column+'"'));
console.log('PASS: measured Weight/Blood/food, velocity units and compass, signed groups, unknown effects/actions, schema isolation and fish exclusion');
