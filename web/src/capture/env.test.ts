import { describe, expect, it } from "vitest";
import { parseUserAgent, platformOf, supportsResizeMode } from "./env";

const UA = {
  androidChrome:
    "Mozilla/5.0 (Linux; Android 14; SM-A145F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
  iphoneSafari:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
  iphoneChrome:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/129.0.6668.69 Mobile/15E148 Safari/604.1",
  macSafari:
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
  winChrome:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
  winEdge:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.2792.65",
  macFirefox: "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:131.0) Gecko/20100101 Firefox/131.0",
};

describe("env", () => {
  it.each([
    [UA.androidChrome, "Chrome 129", "Android 14"],
    [UA.iphoneSafari, "Safari 17.5", "iOS 17.5"],
    [UA.iphoneChrome, "Chrome iOS 129", "iOS 17.5"],
    [UA.winEdge, "Edge 129", "Windows"],
    [UA.macFirefox, "Firefox 131", "macOS 14.5"],
  ])("parses %s", (ua, browser, os) => {
    expect(parseUserAgent(ua)).toMatchObject({ browser, os });
  });

  it("maps platforms, counting a touch Mac as an iPad", () => {
    expect(platformOf(UA.androidChrome, 5)).toBe("android");
    expect(platformOf(UA.iphoneChrome, 5)).toBe("ios");
    expect(platformOf(UA.macSafari, 5)).toBe("ios");
    expect(platformOf(UA.macSafari, 0)).toBe("desktop");
    expect(platformOf(UA.winChrome, 0)).toBe("desktop");
    expect(platformOf("curl/8", 0)).toBe("unknown");
  });

  it("allows resizeMode only on Chromium browsers that report it", () => {
    expect(supportsResizeMode(UA.winChrome, { resizeMode: true })).toBe(true);
    expect(supportsResizeMode(UA.winChrome, {})).toBe(false);
    for (const ua of [UA.iphoneSafari, UA.iphoneChrome, UA.macSafari, UA.macFirefox]) {
      expect(supportsResizeMode(ua, { resizeMode: true })).toBe(false);
    }
  });
});
