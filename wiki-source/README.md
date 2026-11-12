# Wiki source and publishing

The `wiki-source/` directory is the canonical source for the GitHub Wiki. Keep this Wiki focused on short user procedures; the detailed architecture and developer material remains under `docs/`.

## Page rules

- One topic per page.
- Start with a short explanation of what the page covers and when it is useful.
- Keep each bullet to one concept.
- Use **MUST KNOW!!** only for required safety, prerequisite or compatibility information.
- Use **Optional** only for non-essential enhancements.
- Leave basic concepts unlabelled.
- End with a small set of related pages.
- Do not copy private node state, PINs, auth keys or personal network details into examples.

## First-time Wiki activation

GitHub creates the special Wiki repository after its first page is saved.

1. Open the [project Wiki](https://github.com/SilverCrow2323/muOS-Rt-Tailscale/wiki).
2. Create a page named **Home** and save a minimal draft.
3. Run `sh tools/publish_wiki.sh` from a clone with Git credentials.

The publisher copies the reviewed Markdown pages to the special Wiki repository. Edit `wiki-source/`, not only the live Wiki.

## Detailed references

- [Architecture](../docs/ARCHITECTURE.md)
- [Developing for muOS](../docs/DEVELOPING-FOR-MUOS.md)
- [Troubleshooting source](../docs/TROUBLESHOOTING.md)
