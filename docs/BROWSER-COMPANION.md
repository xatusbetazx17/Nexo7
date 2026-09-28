# Mac, iPhone and iPad without installing an app

Nexo's optional browser companion uses the model running on your Windows/Linux PC. It does not run that model on the phone or Mac. No Apple account, App Store installation, Docker or native macOS package is needed.

1. Start Nexo and its local model on the PC.
2. Connect both devices to the same trusted home Wi-Fi.
3. In Settings, open **Open on Mac, iPhone or iPad**. Read the HTTP connection notice, check the consent box, and select **Enable browser companion**.
4. Open the displayed private link in Safari on the other device. Keep the entire link, including its `#key=...` fragment. Treat the link as a password.
5. Ask a question. An image requires the vision model selected on the PC. Questions are independent, not a shared desktop conversation.
6. Select **Stop and revoke link** when finished. Restarting creates a different key. The feature does not start automatically.

The PC must stay awake with Nexo open. On Windows, if a firewall prompt appears, permit the app only on your private network. Guest networks can isolate devices. A new PC network address requires restarting the companion.

## Scope and limits

- Chat and image questions, with local model inference on the PC.
- No desktop settings, email credentials, saved notes, workspace files or unrestricted tools.
- Conversation display is transient in the browser. The key is kept in that tab's session storage; appearance preferences are kept in that browser.
- Uses HTTP on private IPv4 networks; it is **not encrypted**. Use only trusted home Wi-Fi and do not send sensitive information. Do not forward its port to the Internet.
- Desktop UI remains bound to localhost. The companion runs a separate server with an independent revocable key, strict Host/Origin checks and a single chat endpoint. Turning off its permission also disables replies.
- Safari on physical Apple devices has not been tested here. The responsive browser workflow is exercised in Chromium; it does not prove all Safari behavior.

## Appearance

Desktop Settings offers five accent palettes and a custom color, separately from light/dark appearance. My Navi offers robot, cat or orb and an avatar color. Avatar changes are saved in the local Navi profile. The browser companion has its own lightweight color/avatar selectors; it never changes the PC's settings.
