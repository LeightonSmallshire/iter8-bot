// Stub stand-in for the vendored Discord Embedded App SDK.
//
// activity.js imports "/static/vendor/discordSdk.js", a browser absolute path that Node
// cannot resolve, so the test registers a resolve hook pointing that specifier here. Each
// scenario drives behaviour through the globals below.
//
// This mirrors the real SDK v2 shape deliberately: authenticate lives on `commands`, takes
// { access_token: null }, and resolves to { access_token, user, scopes }. It deliberately
// has NO instance-level authenticate, so a regression to the v1 shape fails the test
// instead of only failing inside Discord.

export class DiscordSDK {
  constructor(clientId) {
    globalThis.__activityTest.sdks.push(clientId);

    // v1-style entry point, absent from the real SDK.
    if (globalThis.__activityTest.exposeLegacyAuthenticate) {
      this.authenticate = () => {
        throw new Error("instance-level authenticate must not be used");
      };
    }

    this.commands = {
      authenticate: async (args) => {
        globalThis.__activityTest.calls.push("commands.authenticate");
        globalThis.__activityTest.authArgs = args;
        if (globalThis.__activityTest.fail === "ready") {
          throw new Error("not ready");
        }
        if (globalThis.__activityTest.fail === "emptycode") {
          return { access_token: null, user: null, scopes: [] };
        }
        return {
          access_token: globalThis.__activityTest.token,
          user: { id: "1", username: "tester" },
          scopes: ["identify"],
        };
      },
    };
  }

  async ready() {
    globalThis.__activityTest.calls.push("ready");
    if (globalThis.__activityTest.fail === "authenticate") {
      throw new Error("no handshake");
    }
  }
}