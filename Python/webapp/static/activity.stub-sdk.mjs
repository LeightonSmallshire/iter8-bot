// Stub stand-in for the vendored Discord Embedded App SDK.
//
// activity.js imports "/static/vendor/discordSdk.js", a browser absolute path that Node
// cannot resolve, so the test registers a resolve hook pointing that specifier here. Each
// scenario drives behaviour through the globals below.
//
// This mirrors the real SDK v2 shape deliberately:
//   * authorize lives on `commands`, takes { scopes }, resolves to { code }
//   * authenticate also lives on `commands` but is the OTHER direction -- it accepts an
//     existing access token and will not mint one. Calling it with { access_token: null }
//     makes Discord answer "No access token provided", which is a bug we shipped once.
//     It throws here so that regression fails the tests instead of only in Discord.
//   * there is no instance-level authenticate at all in the real SDK.

export class DiscordSDK {
  constructor(clientId) {
    globalThis.__activityTest.sdks.push(clientId);

    this.commands = {
      authorize: async (args) => {
        globalThis.__activityTest.calls.push("commands.authorize");
        globalThis.__activityTest.authArgs = args;
        if (globalThis.__activityTest.fail === "authorize") {
          throw new Error("no handshake");
        }
        if (globalThis.__activityTest.fail === "emptycode") {
          return {};
        }
        return { code: globalThis.__activityTest.code };
      },

      authenticate: async (args) => {
        globalThis.__activityTest.calls.push("commands.authenticate");
        throw new Error("authenticate cannot mint a token; use authorize");
      },
    };
  }

  async ready() {
    globalThis.__activityTest.calls.push("ready");
  }
}