# recipes/ — Windows-app install recipes

A recipe is a REVIEWED grant of capability to a Windows app (invariant
8: untrusted by default). One TOML per app:

```toml
[recipe]
app = "my-app"                  # slug = prefix dir name
match_sha256 = ["<hex>"]        # pin specific installers, OR
match_installer = "nsis"        # generic per-framework match (no pin)
silent = true
extra_args = []

[grants]                        # DEFAULT DENY — grant only what it needs
network = false                 # true only if the app genuinely needs it
home_paths = []                 # e.g. ["Documents/MyAppSaves"]
```

`home_paths` entries are relative to the user's home and may not contain
`..`, be absolute, or be empty — each of those mounts more of the home
than the grant names, and `home_paths = ["."]` mounts all of it.

**A grant must name something that is already on this machine.** bwrap
resolves a bind's SOURCE on the host, so a grant naming a folder the user
does not have does not degrade the install, it aborts it. jv-compat
therefore refuses the recipe before it builds anything — a `blocked`
frame naming the absolute path — and it will NOT create the folder: only
jv-act writes outside a service's own state dir (invariant 3), and that
folder is the user's. Two ways out, and they are not equal: the user
creates it (one `mkdir`, and the refusal says which), or the recipe grants
a folder that does exist — which for a missing `Documents/MyAppSaves`
means granting `Documents`, handing over every other document with it. The
first is the better answer whenever an app just needs a directory of its
own. A grant may also name a single FILE, which is narrower than the
folder around it.

Both refusals are `jv_compat.prefix.grant_problems`, asked once per
install before a prefix exists, and every bad grant in a recipe is named
at once so one fix covers them all.

Matching: a sha256 pin always wins; otherwise the first pin-less recipe
for the installer framework applies; otherwise a zero-grant default
recipe is synthesized (deny network, private home).

Successful installs should end with the recipe committed here — that's
what makes the app reproducible on a fresh install (blueprint §08).

## What a recipe cannot grant

The rest of the confinement is not a grant and no recipe can widen it:
the app gets its own PID, IPC and UTS namespaces, no controlling
terminal (so an installer cannot reach the shell `jv-compat install` was
typed into), and a fixed machine name — every prefix is told this
computer is called `jarvis-sandbox`. An app that needs any of those back
needs a reviewed change to `jv_compat.prefix`, not a line of TOML.
