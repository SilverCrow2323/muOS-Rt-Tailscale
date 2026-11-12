# Web panel and Taildrop

The web panel lets a phone or PC inspect the service, manage selected settings and use the Taildrop workflow from a browser.

## Open the panel

1. Open the app's **Panel** tab.
2. Read the displayed PIN and scan the QR code, or open the address shown by the app.
3. From the same LAN, use `http://<device-ip>:8077`.
4. From the tailnet, use `http://<tailscale-ip>:8077`.

## Security

> [!IMPORTANT]
> **MUST KNOW!!** The panel uses HTTP on the LAN and the default bind address may listen on all interfaces. Do not forward port 8077 from your router or expose it directly to the public Internet.

- The panel requires its PIN and uses a signed session cookie.
- Five incorrect PIN attempts trigger a temporary lockout.
- Use `./rt pin new` to rotate the PIN and invalidate existing sessions.
- For remote access, prefer **Tailscale Serve**, which provides TLS and Tailscale identity protection.

## Taildrop

Files received through Taildrop are saved under:

```
RtTailscale/taildrop/
```

Check available storage before transferring large files. Do not share the folder publicly if it contains personal data.
