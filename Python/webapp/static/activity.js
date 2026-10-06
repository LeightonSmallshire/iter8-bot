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
// Note the SDK v2 shape: `authorize` (not `authenticate`) lives on sdk.commands, takes
// { scopes: [...] }, and resolves to { code }. `authenticate` is the opposite direction --
// it accepts an existing access token and will not mint one, so calling it with
// { access_token: null } makes Discord answer "No access token provided". The code is then
// traded for a session by /auth/exchange, server-side.
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
    const auth = await sdk.commands.authorize({ scopes: ["identify"] });
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