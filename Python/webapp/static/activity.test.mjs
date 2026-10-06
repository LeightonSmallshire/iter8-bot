// Tests for static/activity.js, the Discord Activity sign-in bootstrap.
//
// activity.js is a classic script that self-executes on import, so each scenario
// re-imports it from a unique data: URL for a fresh run. The SDK import is redirected to
// a stub via activity.loader.mjs, and every scenario gets its own globals and record.
//
// Run with:  node --test "Python/webapp/static/*.test.mjs"   (from the repo root)

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { register } from "node:module";
import test from "node:test";

register("./activity.loader.mjs", import.meta.url);

// activity.js self-executes on import and caches per module URL. Node's ESM cache does
// not reliably treat a query string as a distinct key for file: URLs, so each run is
// imported as a unique data: URL instead -- those are always separate module instances.
const SOURCE = readFileSync(new URL("./activity.js", import.meta.url), "utf8");

const flush = () => new Promise((resolve) => setTimeout(resolve, 20));

// activity.js signals completion by navigating (success) or flagging the status element
// as an error. Wait for that rather than guessing with a fixed sleep.
async function waitUntil(predicate, timeoutMs = 3000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (predicate()) return true;
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  return false;
}

const settled = (record, statusEl) =>
  record.navigations.length > 0 || statusEl.className === "activity-error";

let run = 0;

async function runActivity(env = {}) {
  const {
    framed = true,
    clientId = "12345",
    fail = null,
    exposeLegacyAuthenticate = false,
    exchangeStatus = 200,
    exchangeBody = '{"ok":true}',
  } = env;

  const record = {
    sdks: [],
    calls: [],
    fetchCalls: [],
    authArgs: null,
    navigations: [],
    fail,
    exposeLegacyAuthenticate,
    token: "token-from-sdk",
    exchangeStatus,
    exchangeBody,
  };
  globalThis.__activityTest = record;

  const statusEl = { textContent: "", className: "" };
  globalThis.document = { getElementById: (id) => (id === "activity-status" ? statusEl : null) };

  // In a browser `window` *is* the global object, so a bare `WEBAPP` and `window.WEBAPP`
  // are the same thing. In Node they are not, so publish it on both.
  const win = {};
  win.self = win;
  win.top = framed ? {} : win;
  const webapp = clientId ? { client_id: clientId } : {};
  win.WEBAPP = webapp;
  globalThis.window = win;
  globalThis.WEBAPP = webapp;

  win.location = { href: "/" };
  Object.defineProperty(win.location, "href", {
    get: () => record.navigations.at(-1) ?? "/",
    set: (value) => record.navigations.push(value),
    configurable: true,
  });

  globalThis.fetch = async (url, options) => {
    record.fetchCalls.push({ url, options });
    return {
      ok: record.exchangeStatus >= 200 && record.exchangeStatus < 300,
      status: record.exchangeStatus,
      text: async () => record.exchangeBody,
    };
  };

  run += 1;
  const url = `data:text/javascript;base64,${Buffer.from(`${SOURCE}\n//# run=${run}\n`).toString("base64")}`;
  await import(url);
  await waitUntil(() => settled(record, statusEl));
  await flush();

  return { record, statusEl };
}

test("does nothing in an ordinary browser tab", async () => {
  const { record } = await runActivity({ framed: false });
  assert.deepEqual(record.sdks, []);
  assert.deepEqual(record.fetchCalls, []);
  assert.deepEqual(record.navigations, []);
});

test("does nothing when framed but no client id is configured", async () => {
  const { record } = await runActivity({ clientId: "" });
  assert.deepEqual(record.sdks, []);
  assert.deepEqual(record.fetchCalls, []);
});

test("signs in through the SDK when framed, then opens the shop in-frame", async () => {
  const { record } = await runActivity();

  assert.deepEqual(record.sdks, ["12345"]);
  // SDK v2: authenticate lives on sdk.commands, not on the instance.
  assert.deepEqual(record.calls, ["ready", "commands.authenticate"]);
  assert.deepEqual(record.authArgs, { access_token: null });

  assert.equal(record.fetchCalls.length, 1);
  const call = record.fetchCalls[0];
  assert.equal(call.url, "/auth/exchange");
  assert.equal(call.options.method, "POST");
  // The cookie has to travel; the iframe is a cross-site context.
  assert.equal(call.options.credentials, "include");
  assert.equal(call.options.headers["Content-Type"], "application/json");
  // v2 returns a bearer token, not an authorization code.
  assert.deepEqual(JSON.parse(call.options.body), { access_token: "token-from-sdk" });

  // Stays in the frame: the session cookie belongs to this origin.
  assert.deepEqual(record.navigations, ["/shop"]);
});

test("never calls the v1 instance-level authenticate", async () => {
  // The stub exposes a legacy instance method that throws. Reaching for it is the exact
  // bug that shipped as "sdk.authenticate is not a function".
  const { record, statusEl } = await runActivity({ exposeLegacyAuthenticate: true });

  assert.deepEqual(record.calls, ["ready", "commands.authenticate"]);
  assert.equal(record.navigations.at(-1), "/shop");
  assert.doesNotMatch(statusEl.textContent, /instance-level/);
});

test("surfaces the server's rejection instead of navigating", async () => {
  const { record, statusEl } = await runActivity({
    exchangeStatus: 403,
    exchangeBody: "You're not on the list.",
  });

  assert.deepEqual(record.navigations, []);
  assert.match(statusEl.textContent, /Sign-in failed/);
  assert.match(statusEl.textContent, /not on the list/);
});

test("falls back to the status code when the server sends no detail", async () => {
  const { record, statusEl } = await runActivity({ exchangeStatus: 502, exchangeBody: "" });

  assert.deepEqual(record.navigations, []);
  assert.match(statusEl.textContent, /502/);
});

test("surfaces an SDK handshake failure instead of navigating", async () => {
  const { record, statusEl } = await runActivity({ fail: "authenticate" });

  assert.deepEqual(record.navigations, []);
  assert.match(statusEl.textContent, /Sign-in failed/);
  assert.match(statusEl.textContent, /no handshake/);
  // It must not have tried the exchange if the handshake never completed.
  assert.deepEqual(record.fetchCalls, []);
});

test("treats a missing access token as a failure", async () => {
  const { record, statusEl } = await runActivity({ fail: "emptycode" });

  assert.deepEqual(record.navigations, []);
  assert.deepEqual(record.fetchCalls, []);
  assert.match(statusEl.textContent, /no access token/);
});

test("marks the status element as an error on failure", async () => {
  const { statusEl } = await runActivity({ fail: "authenticate" });
  assert.equal(statusEl.className, "activity-error");
});

test("marks the status element as in-progress while signing in", async () => {
  const { statusEl } = await runActivity();
  assert.equal(statusEl.className, "activity-status");
});