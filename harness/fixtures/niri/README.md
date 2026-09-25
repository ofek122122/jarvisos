# harness/fixtures/niri — what niri really said

`ares-desk.jsonl` is the **real** first six events of
`niri msg --json event-stream`, recorded on ares at 2026-09-25 against the
running session (niri 26.04, three outputs: HDMI-A-1 at 2560x1440 and
DP-1/DP-2 at 1920x1080). One JSON object per line, exactly as niri wrote
them — no hand-written frames, no reordering, nothing pretty-printed.

```
WorkspacesChanged        the opening snapshot: every workspace on every output
WindowsChanged           the same for windows (the bar does not read it)
KeyboardLayoutsChanged   one layout, English (US)
OverviewOpenedOrClosed   the overview was closed
ConfigLoaded             the config niri is running parsed cleanly
CastsChanged             no screencasts
```

## Why it is committed

`shell/jv-bar/core/NiriModel.qml` is the bar's whole claim about the
compositor, and the one way it can be wrong that no unit test written from
memory would catch is **the shape of the line**. A `workspaces` key that is
really `workspace`, an `idx` that is really `index`, a `name` that is
`null` rather than absent — every one of those parses fine, changes
nothing, and leaves a bar that draws no workspaces at all on a machine full
of them. So the opening snapshot in `tests/tst_nirimodel.qml` is this file,
byte for byte, and `tools/tests/test_gen_theme_qml.py` fails if the two
ever stop agreeing.

## What is NOT in it, and why that matters

**Every event here is a snapshot niri sends at connect.** None of the four
deltas the bar acts on is in this recording:

```
WorkspaceActivated            { id, focused }
WorkspaceUrgencyChanged       { id, urgent }
WorkspaceActiveWindowChanged  { workspace_id, active_window_id }
WorkspacesChanged             (again, when workspaces are created or destroyed)
```

They are not here because recording one means **changing the user's live
session** — focusing another workspace, opening a window — and this loop
does not do that to a desk someone is sitting at. Their field names are
therefore not remembered and not guessed: they are read out of the shipped
binary, whose serde field table names them in order, which is a fact about
the `niri` that is actually installed rather than about anybody's memory:

```
$ grep -a -o -P '.{0,120}WorkspaceActivated.{0,200}' \
      $(readlink -f $(which niri)) | head
… idWorkspacesChangedworkspacesWorkspaceUrgencyChangedurgent
  WorkspaceActivatedfocusedWorkspaceActiveWindowChangedworkspace_id …
$ … | grep -o 'struct variant Event::WorkspaceActivated with . elements'
struct variant Event::WorkspaceActivated with 2 elements
```

The arity check is the half that matters: two elements, and `id` is the
interned string those variants share. Everything the model does with a
delta is still inference from a shape, and it is labelled as such in
`NiriModel.qml`. Replacing it with a recording of a real workspace switch
is PLAN **D12**, and it wants a human at the keyboard.
