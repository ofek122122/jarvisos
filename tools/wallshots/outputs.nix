# tools/wallshots/outputs.nix — the outputs the CONTACT SHEET is taken at.
#
# `ops/ralph/wallshots.sh` photographs shell/jv-wall over real art, and until
# PLAN E10 the art it photographed was the machine's: the package rendered five
# fixed geometries, three of which ares cannot display, and the sheet used one
# of those three (2560x1080) for the shot that shows E9's composer working on a
# canvas nobody authored for. E10 made the render list the host's own outputs,
# which is right for the machine — it stops carrying art for monitors it does
# not have — and would have left that shot photographing a fallback instead.
#
# So the sheet declares its own evidence set, and builds `.#jarvis-wallpaper-
# sheet` from it (flake.nix). ares' outputs come in by IMPORT rather than by
# being written again: the sheet must photograph every geometry this machine
# really has — that is most of what it is evidence about — and `++` makes that
# true by construction instead of by a test remembering to compare two lists.
#
# What it adds on top is one geometry ares has no panel for, and the reason is
# specific: 2560x1080 is 21:9, and it is the ONLY place in this repo where a
# render COMPOSED at a non-16:9 canvas can be looked at. Every output ares
# declares is 16:9, so a sheet holding only those would photograph the
# composer's one aspect ratio and assert the rest arithmetically. That shot was
# the picture of PLAN E9's defect (docs/wall/06-ultrawide.png, the before) and
# is now the picture of it fixed; losing it would mean losing the only evidence
# that a 21:9 monitor plugged into this machine gets a whole wordmark.
#
# A 5:4 output is deliberately NOT here. docs/wall/07-fallback.png is the shot
# of the one error path this surface has — a geometry with no bespoke render,
# the Image failing, the primary art cropped to fit — and it only exists
# BECAUSE 1280x1024 is absent from this list. tools/tests/test_wallshots.py
# holds both halves: every shot's caption names the render its geometry
# actually resolves against this list.
import ../../hosts/ares/outputs.nix
++ [
  {
    name = "SHEET-21x9";
    width = 2560;
    height = 1080;
    refresh = "60.000";
    x = 0;
  }
]
