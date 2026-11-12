'use strict';
const assert = require('node:assert/strict');
const m = require('../web/replay-model.js');
const replay = {history_sample_seconds:1,entities:[{id:1,name:'ExamplePlayer',kind:'player',species:'Allosaurus',steam_id:'76561198000000001'}],tracks:{1:[
  [2,100,200,300,1,0,.2,2], [3,400,600,300,1,0,.3,3], [4,400,600,300,0,0,.3,3],
  [9,1000,1000,300,1,0,.4,9], [10,1300,1400,300,1,0,.4,10], [11,1300,1400,300,1,1,.4,10]
]}};
assert.equal(m.frameEntities(replay,1).length,0,'Never show an actor before it exists');
assert.equal(m.frameEntities(replay,3.5)[0].x,400);
assert.equal(m.frameEntities(replay,5)[0].in_scope,false);
assert.equal(m.frameEntities(replay,5)[0].dead,false,'Future death must not leak into past frames');
assert.equal(m.frameEntities(replay,11)[0].dead,true);
const segments=m.routeSegments(replay,1,11);
assert.equal(segments.length,2,'Track must break at lost scope');
assert.equal(m.routeDistance(segments),10,'Do not count unknown travel between separate observations');
assert.equal(m.distanceMeters({x:0,y:0},{x:300,y:400}),5);
assert.equal(m.routeSegments(replay,1,3).length,1,'Never draw a future route');
const active=m.frameEntities(replay,3)[0];
assert.ok(m.matchesFilters(active,{query:active.steam_id.slice(-6),minGrowth:25,maxGrowth:35,species:'Allosaurus',status:'active'}));
assert.ok(!m.matchesFilters(active,{minGrowth:40}));
assert.ok(!m.matchesFilters(active,{species:'Deinosuchus'}));
assert.ok(!m.matchesFilters(active,{players:false}));
assert.ok(m.matchesFilters(m.frameEntities(replay,11)[0],{history:true,status:'dead'}));
const followed=m.followTarget([{...active,id:2,in_scope:false,last_seen:20},{...active,id:3,in_scope:true,last_seen:10}],{steam_id:active.steam_id});
assert.equal(followed.id,3,'Follow the active actor after a player changes GUID');
const csv=m.csv([{...active,name:'=unsafe,"name"'}],3);
assert.ok(csv.includes('76561198000000001'));
assert.ok(csv.includes("'=unsafe,"));
assert.ok(csv.includes('""name""'));
console.log('PASS: timeline existence/scope/death, separated routes, distance units, filters, follow identity and CSV');
