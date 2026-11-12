# FAQ

## Does this app replace the official Tailscale client?

No. It bundles the official ARM64 `tailscale` and `tailscaled` binaries and provides a muOS interface and service manager around them.

## Do I need to install LÖVE first?

No. The application package includes the LÖVE 11.5 runtime it uses.

## How do I log in without typing?

Open **Status → Log in** and scan the QR code with a phone signed in to the account you want to use.

## What happens if the kernel has no TUN device?

The service can fall back to Tailscale userspace networking. Some network-routing capabilities may be more limited than with a working TUN device; check **System → Run diagnostics**.

## Can I use it over SSH without opening the UI?

Yes. The `rt` service manager and `ts` wrapper expose the service and official Tailscale CLI. See [Service and CLI](Service-and-CLI).

## Where do received files go?

Taildrop files are saved under `RtTailscale/taildrop/`.

## Is the web panel safe to expose to the Internet?

No. Do not port-forward port 8077 or expose the HTTP panel directly. Use Tailscale Serve for remote access.

## How do I replace another Tailscale app?

- Shin RtTailscale: install over the existing folder to keep the login and settings.
- Another Tailscale app: use **System → Take over another Tailscale install**.
