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

Matching: a sha256 pin always wins; otherwise the first pin-less recipe
for the installer framework applies; otherwise a zero-grant default
recipe is synthesized (deny network, private home).

Successful installs should end with the recipe committed here — that's
what makes the app reproducible on a fresh install (blueprint §08).
