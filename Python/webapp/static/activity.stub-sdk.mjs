// Stub stand-in for the vendored Discord Embedded App SDK.
//
// activity.js imports "/static/vendor/discordSdk.js", a browser absolute path that Node
// cannot resolve, so the test registers a resolve hook pointing that specifier here. Each
// scenario drives behaviour through the globals below.

export class DiscordSDK {
  constructor(clientId) {
    globalThis.__activityTest.sdks.push(clientId);
  }

  async ready() {
    globalThis.__activityTest.calls.push("ready");
    if (globalThis.__activityTest.fail === "ready") {
      throw new Error("ready refused");
    }
  }

  async authenticate(options) {
    globalThis.__activityTest.calls.push("authenticate");
    globalThis.__activityTest.authOptions = options;
    if (globalThis.__activityTest.fail === "authenticate") {
      throw new Error("no handshake");
    }
    if (globalThis.__activityTest.fail === "emptycode") {
      return {};
    }
    return { code: globalThis.__activityTest.code };
  }
}