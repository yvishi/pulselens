# Status: Yash

Only Yash (and Yash's agent) edits this file. Newest notes first in each section.

## Tasks
- [ ] Y0
- [ ] Y1
- [x] Y2: preflight/probe/face/quality/env; probe skips 1000x750 when resizeMode is unsupported (Safari, all iOS, Firefox); `controls` drops stream keys (width, height, frameRate, deviceId...)
- [ ] Y3
- [ ] Y4
- [ ] Y5
- [ ] Y6
- [ ] Y7
- [ ] Y8
- [ ] Y9
- [ ] Y10

## Decisions

## Measurements

## Blocked

## Needs a human
- Y2: verify the yaw sign on a laptop: run the face tracker, turn to your own left, expect positive `yawDeg`; record the result here (flip `YAW_SIGN` in `web/src/capture/face.ts` if negative). Run `python scripts/fetch_web_models.py` first.
