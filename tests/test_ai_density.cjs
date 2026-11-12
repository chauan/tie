'use strict';
const assert = require('node:assert/strict');
const m = require('../web/replay-model.js');
const bounds = {world_x_min:-100000,world_x_max:150000,world_y_min:-100000,world_y_max:150000};
const ai = (id,x,y,extra={}) => ({id,x:x*100,y:y*100,z:10,kind:'ai',species:'Deer',in_scope:true,dead:false,last_seen:10,...extra});
const entities = [ai(1,-990,-990),ai(2,-510,-510),ai(3,-500,-999),
  ai(4,1499,1499,{species:'Coalecanth'}),ai(5,1500,1500,{species:'Coalecanth'}),
  ai(6,-1000.01,-900),ai(7,1500.01,1490),ai(8,-900,-900,{in_scope:false}),
  ai(9,-900,-900,{dead:true}),ai(10,-900,-900,{kind:'player'}),
  ai(11,-900,-900,{x:NaN}),ai(12,-900,-900,{y:Infinity}),ai(13,0,0,{z:0}),
  ai(2,750,750,{last_seen:20,species:'Boar'}),ai(2,760,760,{last_seen:30,in_scope:false})];
const frozen = JSON.stringify(entities);
const report = m.aiDensity(entities,{bounds,cellMeters:500});
assert.equal(report.total,5,'One active position per AI actor; exclude lost, dead, players, invalid and out-of-map points');
assert.equal(report.cells.length,4);
assert.equal(report.cells[0].count,2);
assert.deepEqual(report.cells[0].species,[{name:'Coalecanth',count:2}]);
assert.deepEqual([report.cells[0].col,report.cells[0].row],[4,4],'Maximum map edge stays in the last cell');
assert.deepEqual(report.cells.slice(1).map(c=>[c.col,c.row]),[[0,0],[1,0],[3,3]],'Ties use stable map order');
assert.equal(report.total,report.cells.reduce((sum,c)=>sum+c.count,0),'Cell totals conserve actor count');
assert.equal(JSON.stringify(entities),frozen,'Never modify replay actors');
assert.equal(m.aiDensity(entities,{bounds,species:'Deer'}).total,2,'Filter after resolving repeated actor positions');
assert.equal(m.aiDensity(entities,{bounds,species:'Boar'}).total,1);
assert.equal(m.aiDensity(entities,{bounds,species:'Missing'}).cells.length,0);
assert.deepEqual(m.aiDensity([],{bounds}).cells,[]);
assert.equal(m.aiDensity(entities,{bounds,cellMeters:0}).cellMeters,500);
for(const cellMeters of [250,500,1000]){
  const result=m.aiDensity(entities,{bounds,cellMeters});
  assert.equal(result.total,5);
  for(const cell of result.cells){
    assert.ok(cell.x>=bounds.world_x_min&&cell.x<=bounds.world_x_max&&cell.y>=bounds.world_y_min&&cell.y<=bounds.world_y_max);
    assert.ok(cell.bounds.xMax-cell.bounds.xMin<=cellMeters*100);
    assert.ok(cell.bounds.yMax-cell.bounds.yMin<=cellMeters*100);
  }
}
const partial=m.aiDensity([ai(1,1499,1499)],{bounds,cellMeters:1000}).cells[0];
assert.deepEqual(partial.bounds,{xMin:100000,xMax:150000,yMin:100000,yMax:150000},'Clip edge cells to real map bounds');
assert.equal(partial.x,125000);
const square=m.aiDensity([ai(1,-999,-999),ai(2,-501,-501)],{bounds});
assert.equal(square.cells.length,1,'A 500 m square is not a 500 m radius cluster');
const replay={entities:[ai(1,-900,-900),ai(2,-800,-800)],tracks:{
  1:[[5,-90000,-90000,10,1,0,.5,5],[10,120000,120000,10,0,0,.5,10]],
  2:[[8,-80000,-80000,10,1,0,.5,8],[12,-80000,-80000,10,1,1,.5,12]]
}};
for(const [time,count] of [[0,0],[5,1],[8,2],[10,1],[12,0]]){
  assert.equal(m.aiDensity(m.frameEntities(replay,time),{bounds}).total,count,`Use only observed AI at timeline ${time}`);
}
console.log('PASS: AI density identity, scope/death, finite coordinates, map edges, species, deterministic ranks, all cell sizes and timeline isolation');
