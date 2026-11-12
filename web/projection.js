(function (root) {
  'use strict';
  // Replay FVector uses X=east, Y=south. The basemap publisher's data files
  // instead use (Lat, Long)=(world Y / 1000, world X / 1000).
  function worldToPixel(point, calibration) {
    if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) return null;
    return {
      x: (point.x - calibration.world_x_min) / (calibration.world_x_max - calibration.world_x_min) * calibration.image_width,
      y: (point.y - calibration.world_y_min) / (calibration.world_y_max - calibration.world_y_min) * calibration.image_height
    };
  }
  function pixelToWorld(point, calibration) {
    if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) return null;
    return {
      x: point.x / calibration.image_width * (calibration.world_x_max - calibration.world_x_min) + calibration.world_x_min,
      y: point.y / calibration.image_height * (calibration.world_y_max - calibration.world_y_min) + calibration.world_y_min
    };
  }
  const api = Object.freeze({worldToPixel, pixelToWorld});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.GatewayProjection = api;
})(globalThis);
