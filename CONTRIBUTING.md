# Contributing

Issues and pull requests are welcome.

1. Run `tests/run_all.sh` before sending a PR (see [docs/DEVELOPING-FOR-KNULLI.md](docs/DEVELOPING-FOR-KNULLI.md)
   section "Testing without a device"). Set `RT_BIN_DIR` to also run the qemu integration test.
2. Keep every user-visible string in English.
3. Shell code is POSIX `sh` (`rt`, `watchdog`, `ts`) and must stay shellcheck-clean; the launcher and
   the service template are bash.
4. If you change behaviour, add or adjust a check in `tests/`, and say in the PR whether you tried it on a real
   muOS device (model and muOS version).

The current release has been verified end-to-end on a real muOS
Andromeda device (launch, controller, init folder, QR login, binary update).
