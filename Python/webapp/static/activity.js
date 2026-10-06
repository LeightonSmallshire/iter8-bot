// Discord Activity bootstrap.
//
// Discord proxies this site through <application id>.discordsays.com and frames it
// inside discord.com. That iframe is a cross-site context, and Discord refuses to have
// its own authorize page framed, so the ordinary "Log in with Discord" link cannot work
// in there. When we detect we are framed we therefore sign in through the Embedded App
// SDK instead: authenticate() returns a bearer token, /auth/exchange validates it against
// Discord and issues a session, and because that request is made from inside the iframe
// the cookie is set on Discord's proxy host where the rest of the app can read it.
//
// Note the SDK v2 shape, per the Embedded App SDK reference:
//   * `authorize` lives on sdk.commands and its AuthorizeRequest REQUIRES `client_id`,
//     with the scopes in a singular `scope` array. Omitting client_id makes Discord
//     answer "No client id provided"; `scopes` (plural) is silently wrong.
//   * it resolves to { code }, which the backend trades for a session.
//   * `authenticate` is the opposite direction -- it accepts an EXISTING access_token and
//     will not mint one, and neither command exists on the SDK instance itself.
//
// In a normal browser tab nothing here runs and the page's own login link is used.

const WEBAPP = window.WEBAPP || {};
const framed = window.self !== window.top;

if (framed && WEBAPP.client_id) {
  startActivity();
}

function status(message, isError) {
  const el = document.getElementById("activity-status");
  if (!el) return;
  el.textContent = message;
  el.className = isError ? "activity-error" : "activity-status";
}

async function startActivity() {
  status("Connecting to Discord…");
  try {
    const { DiscordSDK } = await import("/static/vendor/discordSdk.js");
    const sdk = new DiscordSDK(WEBAPP.client_id);
    await sdk.ready();

    status("Signing in…");
    // Documented shape (AuthorizeRequest): client_id is required, the scope field is
    // singular and an array, and it resolves to { code }.
    //
    // `prompt` is deliberately omitted so Discord can show consent the first time a user
    // authorises and stay silent afterwards; passing "none" fails outright on a first run.
    const auth = await sdk.commands.authorize({
      client_id: WEBAPP.client_id,
      response_type: "code",
      scope: ["identify"],
    });
    const code = auth && auth.code;
    if (!code) throw new Error("Discord returned no authorization code.");

    const response = await fetch("/auth/exchange", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });

    if (!response.ok) {
      const detail = (await response.text()).trim();
      throw new Error(detail || "Sign-in failed (" + response.status + ").");
    }

    // Stay inside the frame: the session cookie lives on this origin.
    window.location.href = "/shop";
  } catch (error) {
    const detail = error && error.message ? error.message : String(error);
    status("Sign-in failed: " + detail, true);
  }
}