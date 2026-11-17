# Controls

Rt:Tailscale-M is designed for the D-pad and the standard SDL game-controller mapping used by muOS Andromeda. The on-screen footer shows button artwork, not a wall of key names.

## Main controls

| Physical control | Action |
|---|---|
| D-pad | Move through rows |
| A | Confirm, open, toggle |
| B | Back, close, cancel |
| X | Set the highlighted online device as exit node |
| Y | Refresh status |
| L1 / R1 | Previous / next tab |
| L2 / R2 | Previous / next tab (trigger-axis support) |
| MENU + START | Quit to the muOS frontend |
| SELECT + START | Compatibility fallback for older layouts |

## Andromeda button names

muOS Andromeda exposes the physical **MENU** button through SDL as the gamepad **Guide** button (`guide`). Rt:Tailscale-M listens for that button together with START, so the normal Andromeda exit shortcut works without stealing MENU by itself.

L2 and R2 are reported by SDL/LÖVE as trigger axes, not ordinary face/shoulder buttons. The app detects a press threshold and treats each trigger as one L1/R1 tab action; holding a trigger does not repeatedly skip tabs.

## Face-button layout

The default artwork follows the Nintendo layout used by many Anbernic handhelds: **A is the right face button and B is the bottom face button**. Open **Settings → Nintendo button layout** to turn the A/B and X/Y swap off for a different physical arrangement.

## Keyboard testing on PC

- Arrow keys: navigate.
- Enter: A / confirm.
- Escape: B / back.
- X and Y: face-button actions.
- Q / E: shoulder actions.
- Ctrl + Q: quit.

The active UI footer is the reference for the current build.
