# TV Home for Samsung NU8000

TV Home is a reversible, offline Web application for an owner-authorized UN65NU8000, targeting Tizen 4.0 and its Chromium M56 engine at 1920 × 1080.
It is **not root, firmware, an OS replacement, a Smart Hub replacement, or a default launcher**.
Smart Hub and the remote's Home button remain Samsung-controlled.
No TV connection, upload, installation, certificate creation, root attempt, exploit, or firmware modification was performed for this implementation.

## What works locally

- Six app shortcuts, two HDMI inputs, local clock/date, clear focus rings, and remote-only navigation.
- Arrows move between tiles; Enter opens; Back opens a cancellable exit dialog.
- Back from an HDMI window closes that window and restores focus.
- App launches use public `tizen.application.launch`.
- HDMI discovers sources with public `tizen.systeminfo.getPropertyValue('VIDEOSOURCE', ...)`, combines its `connected` and `disconnected` arrays, then uses `tizen.tvwindow.setSource`, `show`, and `hide`.
  `VIDEOSOURCE` discovery requires no additional privilege.
- The HDMI window renders behind the transparent Web page; its Back hint hides after five seconds and returns on an arrow or Enter.
- Missing TV APIs display **Demo** and explain why launch or switching cannot work.
- No accounts, credentials, storage, telemetry, external fonts, CDN, backend, or network access.

The runtime requests only `application.launch` and `tv.window` privileges.
Arrows, Enter, and Back are mandatory remote keys, so `tv.inputdevice` registration and privilege are unnecessary.
The dashboard itself is offline; launching a streaming app does not make that separate app offline.

## App setup is intentionally explicit

Five application IDs in `apps/tv-dashboard/settings.js` were verified by WorkBuddy's owner-authorized, read-only inventory on the target TV and supplied for this configuration update.
They are **inventory-verified, not launch-tested**:

| App | Verified installed application ID |
| --- | --- |
| YouTube | `9Ur5IzDKqV.TizenYouTube` |
| Netflix | `org.tizen.netflix-app` |
| Prime Video | `evKhCgZelL.AmazonIgnitionLauncher2` |
| Disney+ | `MCmYXNxgcu.DisneyPlus` |
| Samsung TV Plus | `com.samsung.tv.tvPlusDeeplinker` |

Plex is not installed; its ID remains empty and its tile displays **Setup required**.
The other five tiles display **Open app**, which means configured, not successfully launch-tested.
Store/catalog numbers are not interchangeable with application IDs.
This configuration update did not contact the TV, sign a package, install anything, or perform certificate steps.
Signing and installation remain pending compatible SDK extensions and completion of the Samsung certificate GUI.

For additional apps, obtain the exact installed application ID through a later owner-approved, read-only inventory.
Edit only the corresponding `id` string in `settings.js`, then rebuild and sign the package again.
Do not guess IDs from store URLs, and do not add accounts or credentials to this file.
Keep the six entries to preserve the intended one-row composition.
Unavailable apps fail with an actionable message rather than reporting success.

## Browser demo and checks

Open `apps/tv-dashboard/index.html` directly in Chrome.
No server or package manager is needed.
Use a 1920 × 1080 viewport for the TV composition.
The browser demo cannot launch native TV applications or switch hardware inputs.

Run from the repository root:

```sh
# Standard-library-only package tests and unsigned build.
python3 apps/tv-dashboard/test_package.py
python3 apps/tv-dashboard/package.py
python3 apps/tv-dashboard/package.py --validate apps/tv-dashboard/.work/tv-dashboard/TVHome-unsigned.wgt

# Real-file DOM, keyboard, network, and mocked-TV tests.
# Requires the already-installed Python Playwright package and Google Chrome.
python3 apps/tv-dashboard/test_browser.py

# Existing repository tests and lint, plus the new host scripts.
uv run --frozen pytest -q
uv run --frozen ruff check src tests tools swu apps/tv-dashboard
```

The package builder refuses to overwrite an existing WGT.
For another build, supply a fresh `--output apps/tv-dashboard/.work/tv-dashboard/TVHome-unsigned-v2.wgt` path.
It includes only six runtime files, with `config.xml` at the ZIP root, and rejects extra files, signatures, private keys, wrong platform/profile/privileges, and non-local HTML/CSS assets.
This is **unsigned ZIP/config validation, not Samsung SDK certification or installation validation**.
The generated WGT is not installable until signed with the owner's Samsung certificates.
Build output, WGT files, certificate material, and full screenshots are gitignored.

The browser test writes an actual 1920 × 1080 screenshot to `apps/tv-dashboard/.work/tv-dashboard/dashboard-1920x1080.png`.
Tests exercise the real HTML, CSS, configuration, and JavaScript files, not a reimplemented dashboard.
Mocked hardware results do not establish on-TV compatibility.
All browser network requests are blocked, and tests reject any attempted non-file resource request.
The JavaScript runtime files also passed an Acorn parser configured with `ecmaVersion: 5` using an already-installed local Acorn module.
A modern Chrome run cannot certify M56 rendering or the physical TV's API behavior.

## Installation prerequisites - future owner-approved steps only

1. Use Tizen Studio with Samsung **TV Extensions that explicitly support 2018 TVs / Tizen 4.0** and the Samsung Certificate Extension.
   Do not assume the newest extension supports this older device.
   The exact host SDK/extension combination still needs verification on the owner's installation machine.
2. Have a Samsung Developer account, Samsung author certificate, and Samsung distributor certificate that includes this TV's **DUID**.
   A generic Tizen certificate or another TV's distributor certificate is not sufficient.
   Keep private keys, passwords, profiles, and certificate backups outside the repository.
3. Enable Developer Mode on the owner's TV and authorize the development computer's IP, following Samsung's device instructions.
   A TV restart and same-LAN connectivity may be required.
4. Create a named Samsung certificate profile, such as `TVHome`, in Certificate Manager.
   Preserve the author certificate for future updates.
5. Configure the app IDs before packaging, and sign with that Samsung profile.
   Nothing in the supplied builder creates or automates certificates.

References:

- [Samsung TV SDK setup](https://developer.samsung.com/smarttv/develop/getting-started/setting-up-sdk/installing-tv-sdk.html)
- [Samsung certificates and target DUID](https://developer.samsung.com/smarttv/develop/getting-started/setting-up-sdk/creating-certificates.html)
- [Samsung TV device setup](https://developer.samsung.com/smarttv/develop/getting-started/using-sdk/tv-device.html)
- [Samsung CLI packaging, install, run, and uninstall](https://developer.samsung.com/smarttv/develop/getting-started/using-sdk/command-line-interface.html)
- [Public TVWindow API](https://docs.tizen.org/application/web/api/4.0/device_api/tv/tizen/tvwindow.html)

### Sign a clean runtime directory

These commands are instructions only and were not executed against a TV or certificate store.
After creating the unsigned WGT above, extract its validated runtime files into a new ignored directory, then sign that directory using the SDK:

```sh
python3 apps/tv-dashboard/package.py --validate apps/tv-dashboard/.work/tv-dashboard/TVHome-unsigned.wgt
python3 -m zipfile -e apps/tv-dashboard/.work/tv-dashboard/TVHome-unsigned.wgt apps/tv-dashboard/.work/tv-dashboard/signing-source
tizen package -t wgt -s TVHome -- apps/tv-dashboard/.work/tv-dashboard/signing-source
```

Use the signed WGT path actually printed by `tizen package`; do not rename the unsigned WGT and call it signed.
Inspect the signed archive for `author-signature.xml` and `signature1.xml` and keep it untracked.
The presence of signature files alone does not prove certificate validity or DUID authorization.
Only a successful authorized installation establishes that the device accepts the signatures.

Some SDK/device combinations require an install permit.
Use Device Manager's **Permit to install applications** action if required.
If that SDK provides an `install-permit` CLI command, inspect `tizen install-permit --help` and use its version-specific target/profile arguments.
No install permit has been requested by this implementation.

### Install, run, uninstall

Set `TV_TARGET` to the owner-approved target name shown by Tizen Studio's Device Manager.
Set `SIGNED_WGT` to the real signed output path from the previous step.
These commands contact the TV and must only be run during an explicitly authorized device session:

```sh
TV_TARGET='your-target-name'
SIGNED_WGT='/absolute/path/to/the-actual-signed-output.wgt'

tizen install -t "$TV_TARGET" --name "$(basename "$SIGNED_WGT")" -- "$(dirname "$SIGNED_WGT")"
tizen run -t "$TV_TARGET" -p TvHome0001.TVHome

# Rollback removes only this application.
# Samsung TV uninstall uses the application ID, not the package ID.
tizen uninstall -t "$TV_TARGET" -p TvHome0001.TVHome
```

The application ID is `TvHome0001.TVHome`; the package ID is `TvHome0001`.
Keep both stable when signing updates.
Uninstalling TV Home does not uninstall streaming apps or change firmware.
HDMI source selection can change the TV's current source; exiting the dashboard does not promise to restore the previously selected channel/input.
Use Samsung's Source menu to choose the desired source after exit.

## Startup limitations

Samsung's **Autorun Last App** setting is firmware- and application-dependent.
It may resume the most recently used eligible app; it does not establish TV Home as a permanent launcher.
TV Home does not modify that setting, intercept Home, disable Smart Hub, or guarantee cold-boot launch.
Manual launch from the installed-app list is the baseline.

## On-TV acceptance still required

- Confirm the chosen legacy TV Extension, certificate profile, DUID, signing, and optional installation permit work with this firmware.
- Install the signed WGT and confirm the local icon, name, 1920 × 1080 layout, readable text, clock, and focus safe margins on the physical screen.
- Navigate every tile using only arrows, Enter, and Back; cancel and confirm exit.
- Configure and launch one genuinely installed app first; verify missing IDs and unavailable apps report errors.
- Connect one HDMI source first; validate source numbering, picture, sound, transparent video layer, hint timeout, and Back cleanup.
- Test a disconnected HDMI input, denied/unsupported TV APIs, repeated Enter, Home/background, and returning to TV Home.
- Confirm Smart Hub and the normal Source menu remain usable, then uninstall TV Home and verify the ordinary TV experience remains intact.
- Treat Autorun Last App as optional and unverified, not an acceptance condition for a default launcher.

Validate that small on-TV sample before enabling other app IDs or testing more inputs.
Do not infer device success from mocked browser tests.
