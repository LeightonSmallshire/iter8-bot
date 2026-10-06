# Vendored third-party assets

## discordSdk.js

Discord Embedded App SDK, **v2.5.0**.

- Source: `https://cdn.jsdelivr.net/npm/@discord/embedded-app-sdk@2.5.0/+esm`
- Upstream package: [`@discord/embedded-app-sdk`](https://www.npmjs.com/package/@discord/embedded-app-sdk)
- SHA-256: `DD8AF70DCE364EA438BB8821380F3A2E14F10749C2A936B94D240ED51848D7EE`

Kept byte-identical to what jsDelivr serves, so the hash above stays verifiable. Do not
hand-edit it.

Used by `Python/webapp/static/activity.js` to authenticate inside a Discord Activity
iframe. The bundle exposes a **named** export, so import it as:

```js
import { DiscordSDK } from "/static/vendor/discordSdk.js";
```

Vendored rather than loaded from a CDN at runtime because this repo has no JS build
step, and the Activity should not depend on a third-party CDN being reachable from
Discord's proxy.

To upgrade, bump the version in the URL, re-download, update the hash above, and re-test
the Activity in a real Discord client.