// Resolve hook so activity.js's browser-absolute SDK import resolves to the stub.
// Registered by activity.test.mjs before activity.js is imported.

const STUB = new URL("./activity.stub-sdk.mjs", import.meta.url).href;

export function resolve(specifier, context, nextResolve) {
  if (specifier === "/static/vendor/discordSdk.js") {
    return { url: STUB, shortCircuit: true };
  }
  return nextResolve(specifier, context);
}