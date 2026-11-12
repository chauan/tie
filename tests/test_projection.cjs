'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {worldToPixel, pixelToWorld} = require('../web/projection.js');
const calibration = JSON.parse(fs.readFileSync(path.join(__dirname, '../web/assets/gateway-calibration.json'), 'utf8'));

// Independent anchors: named Lat/Long from VulnonaMAP's Gateway data_1.txt,
// reference pixels from the publisher's game2map logical canvas (2780x2790)
// resized to this image. Input here is replay FVector (Long*1000, Lat*1000).
const landmarks = [
  ['East Lake', 460000, -137000, 3384.442446043, 1645.842293907],
  ['Delta', 177000, 33000, 2391.906474820, 2241.146953405],
  ['Water Access', 87000, -214000, 2076.258992806, 1376.204301075],
  ['South Plains', -302000, 250000, 711.960431655, 3001.035842294],
  ['Central Dome', -43000, 104000, 1620.323741007, 2489.774193548],
];
for (const [name, x, y, expectedX, expectedY] of landmarks) {
  const actual = worldToPixel({x, y}, calibration);
  assert.ok(Math.abs(actual.x - expectedX) < 1e-6, `${name}: horizontal axis misplaced`);
  assert.ok(Math.abs(actual.y - expectedY) < 1e-6, `${name}: vertical axis misplaced`);
  const inverse = pixelToWorld(actual, calibration);
  assert.ok(Math.abs(inverse.x - x) < 1e-6 && Math.abs(inverse.y - y) < 1e-6, `${name}: cursor inverse differs from marker`);
}
const origin = worldToPixel({x: 0, y: 0}, calibration);
const east = worldToPixel({x: 100000, y: 0}, calibration);
const south = worldToPixel({x: 0, y: 100000}, calibration);
assert.ok(east.x > origin.x && east.y === origin.y, 'Replay X must move east, never vertically');
assert.ok(south.y > origin.y && south.x === origin.x, 'Replay Y must move south, never horizontally');
assert.deepEqual(worldToPixel({x: -505000, y: -607000}, calibration), {x: 0, y: 0});
assert.deepEqual(worldToPixel({x: 607000, y: 509000}, calibration), {x: 3900, y: 3908});
assert.equal(worldToPixel({x: NaN, y: 0}, calibration), null);
console.log(`PASS: ${landmarks.length} external coordinate anchors, east/south direction, bounds and cursor inverse`);
