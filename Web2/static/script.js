// script.js
import { authenticate, getPlatformInformation } from "https://unpkg.com/@discord/embedded-app-sdk@1.5.1/build/fn.js";

const client_id = "1425483577587531886";

async function initDiscordActivity() {
    const statusEl = document.getElementById('status');
    const userIdEl = document.getElementById('user-id');
    const fastapiMsgEl = document.getElementById('fastapi-message');

    statusEl.textContent = "Authenticating...";

    try {
        // 1. Authenticate with Discord
        const { access_token, user } = await authenticate({ client_id });

        statusEl.textContent = "Authenticated!";
        userIdEl.textContent = user.id;

        // Optionally, fetch more info or set an activity here using the SDK functions
        const platform = await getPlatformInformation();
        console.log("Platform Info:", platform);

    } catch (error) {
        console.error("Discord Authentication Failed:", error);
        statusEl.textContent = `Authentication Failed: ${error.message}`;
    }

    // 2. Call the FastAPI Backend
    try {
        const response = await fetch("/api/hello");
        const data = await response.json();
        fastapiMsgEl.textContent = data.message;
    } catch (error) {
        console.error("FastAPI Backend Call Failed:", error);
        fastapiMsgEl.textContent = `Backend Failed: ${error.message}`;
    }
}

initDiscordActivity();
