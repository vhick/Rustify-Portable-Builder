# Source audit and verification record (13 November 2026)

## Upstream release

- Repository: https://github.com/PabloSoage/Rustify
- Latest visible release during audit: `v5.6.4-beta`, from 6 November 2026, short commit `94b3e20`. The builder resolves the **full 40-character tag commit SHA** at runtime; no unverified `main` builds.
- Upstream description: Rust core + Kotlin / Compose Multiplatform desktop JVM + Windows jpackage portable distributable; desktop signing is not provided.
- Official Windows file naming: `Rustify-<version>-windows-x86_64-portable.zip` in upstream release assets. The original upstream CI's `release.yml` adds a `portable` marker to the jpackage directory and packages `Rustify/`.
- Source code license: `GPL-3.0`; upstream README acknowledges its original graphic logo is based on the Lightkeepers logo from Genshin Impact, so this kit supplies an **original independently drawn generic musical-note icon** rather than redistributing a potentially restricted graphic in PortableApps metadata.
- Upstream desktop `build.gradle.kts` compiles `core_engine.dll` with `desktop-audio,media-controls,secure-store,window-style` and a `rustify-login.exe` helper from source, embeds a Java runtime with jpackage, and uses `java.prefs` for installed mode.
- Source lock identities: `core_engine/Cargo.lock`, `gradle/libs.versions.toml`, `gradle/wrapper/gradle-wrapper.properties`, and `desktopApp/build.gradle.kts`, SHA-256 recorded per release in `BUILD-IDENTITY.json`. The official compiled binary provenance is the developer's GitHub release asset, not a local source rebuild.
- No Android SDK, Rust toolchain, or JDK required to create our package. Runtime dependencies are inherited from the official Windows portable distribution.

## Pinned shared-action baselines, SOURCE-INSPECTED

| Component | Version | Full immutable commit | Contract |
|---|---|---|---|
| `vhick/Portable-Package-Builder` | `v1.0.0` | `0112c35580e83b37eb8757ebcb949274e1631a04` | `source-dir`, `output-dir`, `engine`, `running-exe`, `timeout-seconds`, `package-revision`; `installer-file`, `installer-sha256`, `app-id`, `app-version` outputs. Validates PE and installer archive. |
| `vhick/portable-release-publisher` | `v1.1.1` | `cb64f86ac2d8c67506db5832de07f9ff58cbeaeb` | `files`, `tag`, `release-title`, `tag-prefix`, `keep-releases`, `prune`, `dry-run`. Publishes only `.zip`/`.paf.exe`, private-to-private by targeting calling repo, checks existing release checksum, creates `SHA256SUMS.txt`. |

**Never label a custom-NSIS result an official PortableApps.com-certified installer.** Installer generation and release publication occur only inside GitHub Actions; source was verified independently from both exact tagged action.yml files, build.ps1, common.ps1, NSIS template, and publish.py.

## Security validation boundaries

- Release API selects numeric semantic versions and filters beta/prerelease as requested. `stable` mode fails clearly while no Windows stable portable release exists; `beta` is a deliberate explicit choice. Explicit tag and selected channel must agree.
- GitHub 404 for a named release is a meaningful error; 401/403/rate limit/server failures abort, never imply there are no releases.
- Tag is resolved to commit through the GitHub git/ref API, including annotated tags.
- Developer ZIP must have a GitHub-published SHA256 asset digest, match its API byte length, and have the exact `Rustify/Rustify.exe` portable layout/marker. A changed source portability implementation aborts rather than falling back to unsafe profile paths.
- ZIP extraction rejects unexpected roots, path traversal, symlink entries and oversized archives. Upstream application executable must be **x64 PE**.
- The root launcher must be a real **x64 compiled PE**, created by MSVC on the hosted Windows runner. The installer binary may legitimately be x86 NSIS; it is checked as PE independently.
- PortableApps appinfo uses a numeric four-part package version without reclassifying beta as stable.
- Embedded evidence records the chosen channel, actual upstream version/tag/commit, asset digest, source file hashes, builder commit and package/builder revisions.
- ZIP includes explicit empty `Data\RustifyProfile\cache` and `data\settings` directory entries. The custom-NSIS installer purposefully does **not** embed Data so reinstall/upgrade cannot replace user state.
- Shared publisher dry-run is mandatory, publishing is optional (dispatch checkbox), pruning disabled, `keep-releases=3`, minimum job token permission `contents:write` to make a release.
- Same source commit + same ZIP digest + same builder commit yields the same tag to prevent accidental duplicate. Release publisher rejects a collision with different assets rather than overwriting or deleting it.
- The optional installer-only workflow downloads an existing release **from the same builder repository**, verifies managed-release marker and SHA256SUMS, leaves the original ZIP release intact and publishes any new installer under a new r3 tag.

## Current evidence matrix

| Check | Status | Evidence / unmet condition |
|---|---|---|
| Upstream source and portable design | SOURCE-INSPECTED | `AppDirs.kt`, `DesktopStores.kt`, `UrlScheme.kt`, `Main.kt`, desktop Gradle, upstream release workflow |
| Pinned shared action interfaces | SOURCE-INSPECTED | Tag-specific raw action.yml, shared scripts and immutable full SHA |
| Python resolver/archiver security fixtures | STATIC-VALIDATED | Local unittest suite completed 12/12 |
| GitHub Actions schema basic syntax | STATIC-VALIDATED after local YAML parse; not an executed workflow | No GitHub Actions remote run yet |
| Developer asset download verification | NOT YET VERIFIED end-to-end | GitHub runner must fetch and digest-verify official 100+ MB ZIP |
| Root x64 launcher compilation | NOT YET VERIFIED | Requires Windows hosted runner with MSVC |
| Complete PortableApps ZIP creation | NOT YET VERIFIED | Requires verified developer asset and compiled launcher |
| Rustify GUI and data/session persistence | NOT YET VERIFIED | Real Windows GUI run required |
| TraceGuard and ShellGuard | NOT IMPLEMENTED — not evidence-required | Verified portable profile and URL-scheme skip; no indiscriminate harvesting |
| Notification click-to-open | NOT YET VERIFIED | Windows user-session test required |
| Installed Rustify coexistence | NOT YET VERIFIED | Side-by-side before/after host comparison |
| Custom-NSIS installer generation | NOT YET VERIFIED | Requires workflow shared action |
| Installer install/reinstall/upgrade | NOT YET VERIFIED | Actual Windows interactive exercise |
| Shared publisher dry-run and real publication | NOT YET VERIFIED | Requires builder repo Actions run and authorized release publication |
| NATIVE, autostart, appbar | NOT APPLICABLE | Only PORTABLEAPPS selected |

## Primary references

- https://github.com/PabloSoage/Rustify/releases/tag/v5.6.4-beta
- https://raw.githubusercontent.com/PabloSoage/Rustify/v5.6.4-beta/shared/src/desktopMain/kotlin/com/varuna/rustify/platform/AppDirs.kt
- https://raw.githubusercontent.com/PabloSoage/Rustify/v5.6.4-beta/shared/src/desktopMain/kotlin/com/varuna/rustify/platform/DesktopStores.kt
- https://raw.githubusercontent.com/PabloSoage/Rustify/v5.6.4-beta/sharedUi/src/desktopMain/kotlin/com/varuna/rustify/ui/UrlScheme.kt
- https://raw.githubusercontent.com/PabloSoage/Rustify/v5.6.4-beta/desktopApp/build.gradle.kts
- https://raw.githubusercontent.com/PabloSoage/Rustify/v5.6.4-beta/.github/workflows/release.yml
- https://raw.githubusercontent.com/vhick/Portable-Package-Builder/v1.0.0/action.yml
- https://raw.githubusercontent.com/vhick/portable-release-publisher/v1.1.1/action.yml

## b1r2 compile failure fix evidence

Uploaded b1r1 GitHub Actions run `logs_117437247708.zip` stopped at `scripts/compile-launcher.ps1:9` with `The variable '$LASTEXITCODE' cannot be retrieved because it has not been set.` This is a strict-mode script error, not proof of an upstream application failure. b1r2 checks the explicit `vswhere` process ExitCode and avoids reading an unset automatic variable. Further Windows compile and runtime verification pending.
