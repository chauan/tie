# Gateway map sources

The viewer uses the Gateway basemap published by **VulnonaMAP / Coco.N (Ciro)**. Underlying game imagery belongs to **The Isle / Afterthought LLC**. This third-party image is excluded from the Git repository. `bootstrap-map.ps1` downloads the pinned image from its publisher for the local viewer; no redistribution license for the imagery is asserted here.

- Publisher: https://vulnona.com/game/map/
- Image: https://vulnona.com/game/map/map/Gateway_v0.21.7/base/3.webp
- Calibration: https://vulnona.com/game/map/map/Gateway_v0.21.7/data_1.txt
- Provider projection: https://vulnona.com/game/map/js/map.js (`game2map`)
- Size: 3900 x 3908 pixels, 2,525,028 bytes.
- SHA256: `4019299d2bf365ff8c8aa2063ad195317edc0d6da3ad39f4815c5d82c2b66611`.

Calibration is recorded in `web/assets/gateway-calibration.json`. Replay X increases east/right; Y increases south/down. Provider latitude equals replay Y / 1000 and longitude equals replay X / 1000. The provider's latitude/longitude axis swap must not be applied directly to raw replay X/Y.

```text
pixel_x = (world_x + 505000) / 1112000 * 3900
pixel_y = (world_y + 607000) / 1116000 * 3908
```

The pixel origin is top-left. Tests cover named landmarks, coordinate bounds, axis direction and inverse projection. Calibration has been compared with publisher configuration and landmarks; exact visual agreement with every game revision has not been established. The pinned basemap is labeled Gateway v0.21.772.
