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
// Note the SDK v2 shape: authenticate lives on sdk.commands, takes
// { access_token: null } to request a fresh token (there is no scope argument), and
// resolves to { access_token, user, scopes } -- a token, not an authorization code.
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
    const auth = await sdk.commands.authenticate({ access_token: null });
    const accessToken = auth && auth.access_token;
    if (!accessToken) throw new Error("Discord returned no access token.");

    const response = await fetch("/auth/exchange", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_token: accessToken }),
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