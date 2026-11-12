# Uninstall and recovery

Use the in-app shutdown controls before removing the application so its boot hook and background service are stopped cleanly.

## Normal uninstall

1. Open **Settings → Start at boot** and switch it off.
2. Open **System → Stop everything**.
3. Exit the app.
4. Delete the installed `MUOS/application/RtTailscale/` directory.

## Reset the local identity

- To sign out, use **Status → Log out of this tailnet**.
- To forget the device completely, stop the service, remove the local `state/` directory, then remove the device from the Tailscale admin console before logging in again.
- To reset settings, remove `config/rt.conf`.

> [!IMPORTANT]
> **MUST KNOW!!** Deleting `state/` removes the local node identity. Do not do this as a routine troubleshooting step. Keep a private backup only if you understand that it contains credentials.

## Related guide

See [Troubleshooting](Troubleshooting) before removing data.
