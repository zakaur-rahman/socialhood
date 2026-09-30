import { describe, expect, it } from "vitest";

import { base64UrlToBytes, detectPlatform, deviceSupport, readEnvironment, sameKey, type PushEnvironment } from "./support";

const IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1";
const ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36";
const MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15";

function env(overrides: Partial<PushEnvironment>): PushEnvironment {
  return { platform: "desktop", standalone: false, pushApis: true, permission: "default", ...overrides };
}

describe("push support (FR-NOT-03, TR-FE-09)", () => {
  it("tells iPhone, iPad, Android and computers apart", () => {
    expect(detectPlatform({ userAgent: IPHONE })).toBe("ios");
    expect(detectPlatform({ userAgent: MAC, platform: "MacIntel", maxTouchPoints: 5 })).toBe("ios"); // iPadOS
    expect(detectPlatform({ userAgent: MAC, platform: "MacIntel", maxTouchPoints: 0 })).toBe("desktop");
    expect(detectPlatform({ userAgent: ANDROID })).toBe("android");
  });

  it("an iPhone Safari tab has to install first; the Home Screen app without the APIs is too old", () => {
    expect(deviceSupport(env({ platform: "ios", pushApis: false }))).toBe("ios-install");
    expect(deviceSupport(env({ platform: "ios", pushApis: false, standalone: true }))).toBe("unsupported");
    expect(deviceSupport(env({ platform: "ios", pushApis: true, standalone: true }))).toBe("supported");
    expect(deviceSupport(env({ platform: "desktop", pushApis: false }))).toBe("unsupported");
    expect(deviceSupport(env({ platform: "android" }))).toBe("supported");
  });

  it("reads the browser: jsdom has no push APIs", () => {
    const read = readEnvironment(window);
    expect(read.pushApis).toBe(false);
    expect(read.permission).toBe("unsupported");
  });

  it("decodes the VAPID key and compares it with a subscription's", () => {
    const key = "BAECAwQ"; // bytes 4, 1, 2, 3, 4
    expect(Array.from(base64UrlToBytes(key))).toEqual([4, 1, 2, 3, 4]);
    expect(Array.from(base64UrlToBytes("-_8"))).toEqual([251, 255]);
    expect(sameKey(new Uint8Array([4, 1, 2, 3, 4]).buffer, key)).toBe(true);
    expect(sameKey(new Uint8Array([4, 1, 2, 3, 5]).buffer, key)).toBe(false);
    expect(sameKey(null, key)).toBe(true);
  });
});
