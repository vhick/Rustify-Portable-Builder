# Rustify PortableApps runtime/data contract — b1r1

**Mode: PORTABLEAPPS only.** No native/source-rebuilt app is produced. The actual Rustify application in the final package is the official developer's Windows x64 portable release, verified against the GitHub release asset's SHA-256 digest. The package's root launcher is compiled from readable C++ source on the Windows runner.

## App-specific storage map

| Item | Evidence/owner | Normal installed location or behavior | PortableApps behavior | Protection/limitation |
|---|---|---|---|---|
| Main persistent data/history/player/queue | SOURCE-INSPECTED `shared/.../AppDirs.kt` and `desktopApp/.../Main.kt` | `%APPDATA%\Rustify` | `RUSTIFY_PORTABLE_DIR=<package>\Data\RustifyProfile`, writes under `Data\RustifyProfile\data` | Launcher sets variable before creating the JVM process; no host-profile migration |
| Cover art, cache | SOURCE-INSPECTED `shared/.../AppDirs.kt` | `%LOCALAPPDATA%\Rustify\cache` | `Data\RustifyProfile\cache` | Empty cache trees retained in ZIP; actual runtime not yet observed |
| Desktop settings | SOURCE-INSPECTED `shared/.../DesktopStores.kt` | Java Preferences under current user's registry | `Data\RustifyProfile\data\settings` via upstream `FileStore` | Does not import installed Rustify preferences; protects coexistence |
| `rustify://` URL protocol | SOURCE-INSPECTED `sharedUi/.../UrlScheme.kt` | `HKCU\Software\Classes\rustify` | Upstream returns before registration in portable mode | Existing installed associations are left untouched; portable copy may not receive browser links |
| Spotify authentication cookie/token | SOURCE-INSPECTED `AppDirs.kt` comments and Rust `secure-store` build feature | OS-secured credential store | Still OS-secured, **not portable** | Sign in on each PC; do not export, disable, delete, or harvest Windows credentials |
| Sign-in helper window | SOURCE-INSPECTED `desktopApp/build.gradle.kts` | `rustify-login.exe`, system webview | Remains bundled under `App\Rustify` | OS webview/browser may create Windows-managed caches; complete runtime testing required |
| Single-instance/tray lifecycle | SOURCE-INSPECTED `desktopApp/.../Main.kt` | One instance per selected data folder; tray process | Launcher waits for launched Rustify.exe; args forwarded; profile unique | No broad process kill; background child closure not yet runtime-verified |
| Music downloads, local library directories | README + INFERRED behavior | User-selected filesystem locations | Remain user-selected | For full mobility, manually choose a directory inside `Data`; portable launcher never copies personal folders |
| Self-update | README; automated updater behavior NOT FULLY SOURCE-INSPECTED | Offers release installer/download | **Do not run an in-app installer/update on the portable copy** | Update through this builder's ZIP/PAF; an upstream installer could affect installed Rustify |
| AUMID/notifications/Jump Lists | Windows/framework INFERRED | OS-managed state possible | No application-owned shell cleanup is attempted | Notification activation, Explorer caches, and Windows history require interactive acceptance |
| Shortcuts and installer state | SOURCE-INSPECTED pinned shared NSIS script | Installer may write shortcuts | Independent NSIS does **not** create shortcuts or registry keys; preserves Data | Shared installer touches managed App/Other/root launcher only; inspect backup on interruption |

## Why no TraceGuard or ShellGuard harvesting?

The developer already provides portable-profile routing, and the Windows URL-protocol code explicitly disables registration for portable mode. There is no established application-specific external file or registry allowlist to harvest safely. Broad AppData/registry harvesting would endanger installed Rustify profiles and is intentionally omitted. Windows-managed browser/notification history and machine-bound credentials are documented limitations, not data silently deleted. Add narrow recovery ONLY after reproducible Process Monitor/Registry observations establish exclusive ownership and non-destructive recovery rules.

## Launcher responsibilities

The C++ root launcher resolves its own location with `GetModuleFileNameW`, validates that `Data` and `Data\RustifyProfile` are real directories, rejects junction/symlink redirects at those entry points, sets `RUSTIFY_PORTABLE_DIR` *inside its own process only*, calls the bundled `App\Rustify\Rustify.exe` with correctly quoted Unicode arguments, inherits only per-process environment, waits for that application process to return, and forwards its exit status. No permanent registry/startup/service/driver entries, self-update, or global environment variables are changed by the launcher.

## Safe upgrades and rollback

1. Close Rustify completely, including its tray process; otherwise an in-use-executable check may abort safely.
2. Back up **all** of `RustifyPortable\Data` (including hidden and completely empty directories) before any upgrade. Keep at least one known-good ZIP and the upstream release tag/digest.
3. Preferred: run the shared custom-NSIS installer into the *same* `RustifyPortable` directory. Its source code stages `App`, `Other`, and root launcher, backs up the previous managed files, and never overwrites `Data`. It leaves a `.__UPB_Backup` on interrupted transactions for inspection.
4. ZIP/manual upgrade: extract NEW package separately, then replace only `App`, `Other`, and `RustifyPortable.exe` in an existing package after Rustify exits. **Never replace or delete the existing `Data`**. Ensure no junctions or symlinks before replacing directories.
5. After any rollback, restore the matching `Data` backup too if a new version changed data schemas. Merely downgrading binaries can be unsafe.
6. Moving folder/USB drive letters should work for file-based state through the local profile variable; user-selected absolute music paths and machine-bound credentials may need reconfiguration.

## Interactive Windows acceptance checklist (NOT performed by CI)

- Windows 10 and Windows 11 x64, local disk and USB drive, Unicode path and folder with spaces.
- First launch, sign-in, player functionality, tray minimize/close/exit, duplicate launch and CLI/`rustify://` forwarding.
- Restart and compare settings, history, playlist, cache and nested *empty* directory trees in `Data`.
- With a separately installed Rustify already configured, compare `%APPDATA%\Rustify`, `%LOCALAPPDATA%\Rustify`, `HKCU\Software\Classes\rustify`, user Java preferences and Start Menu shortcuts before/after portable runs. Confirm NO installed profile altered.
- Process Monitor on the exact launch and shutdown to identify unexpected Java/webview/credential/notification writes. DO NOT delete unidentified traces.
- Native Windows notification delivery/click-to-open, media controls, browser/webview sign-in, Explorer restart, fullscreen and monitor/DPI changes where relevant.
- Force-close, crash, full process tree termination and next launch; confirm application data survives.
- Install fresh, installer reinstall, upgrade, rollback and folder relocation; verify `Data` and all empty directories survive.
- Test user-selected music download directories; do not assume personally chosen external paths are movable.

**Evidence:** Source inspection of the v5.6.4-beta code paths and pinned shared action sources; local Python unit tests. Windows compilation, actual application runtime, interactive shell tests, installer execution and publication remain to be verified by a real workflow run and Windows user testing.
