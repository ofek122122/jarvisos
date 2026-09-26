// What niri said, for every driver in this harness (PLAN D34).
//
// There are two files in `scene/` that drive the real bar — the contact sheet
// and the settle — and both need the same thing to start from: a line the
// compositor wrote. A QML engine cannot read a file out of the repository, so
// the recording below is a COPY, and a copy that existed twice would be a copy
// that drifts twice. It lives here, once, and `tools/tests/test_barshots.py`
// holds it to `harness/fixtures/niri/ares-desk.jsonl`.
//
// The failure this guards against is the one no desk written from memory
// catches: `idx` that is really `index`, a `name` that is absent rather than
// null. Every one of those parses, changes nothing, and leaves a driver
// asserting against a bar that is empty for a reason the real one never has.
import QtQuick

QtObject {
  id: root

  // harness/fixtures/niri/ares-desk.jsonl line 1, verbatim: ares' three
  // monitors as niri described them at connect.
  //
  // Worth knowing what it happens to contain: HDMI-A-1's workspaces arrive in
  // the order 2, 1, so a bar that trusted niri's order would draw this desk as
  // "2 1". `docs/bar/01-primary.png` is the picture of that not happening.
  readonly property string recorded: '{"WorkspacesChanged":{"workspaces":[{"id":2,"idx":1,"name":null,"output":"DP-1","is_urgent":false,"is_active":true,"is_focused":false,"active_window_id":null},{"id":3,"idx":1,"name":null,"output":"DP-2","is_urgent":false,"is_active":true,"is_focused":false,"active_window_id":null},{"id":4,"idx":2,"name":null,"output":"HDMI-A-1","is_urgent":false,"is_active":false,"is_focused":false,"active_window_id":null},{"id":1,"idx":1,"name":null,"output":"HDMI-A-1","is_urgent":false,"is_active":true,"is_focused":true,"active_window_id":2}]}}'

  // A desk ares does not have, in the shape of the one it does. Every key here
  // is a key of the recorded line above, which a tools test holds, so a
  // composed desk cannot quietly be a picture of a message format niri does
  // not use. `name` is niri's own field — `null` for the ordinary unnamed
  // workspace, the string for one the user named in their config.
  function snapshot(rows: var): string {
    const out = [];
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i];
      out.push({
        "id": r.id,
        "idx": r.idx,
        "name": r.name === undefined ? null : r.name,
        "output": r.output,
        "is_urgent": r.urgent === true,
        "is_active": r.active === true,
        "is_focused": r.focused === true,
        "active_window_id": null
      });
    }
    return JSON.stringify({ "WorkspacesChanged": { "workspaces": out } });
  }

  // One workspace becoming the active one on its output, and one asking for
  // you. niri's own two deltas, spelled as it spells them — neither is in the
  // recording (it is a connect snapshot, and recording a delta means
  // rearranging a desk someone is sitting at, PLAN D12), so these are the one
  // place the bar's moving parts are driven rather than described.
  function activated(id: int, focused: bool): string {
    return JSON.stringify({ "WorkspaceActivated": { "id": id, "focused": focused } });
  }

  function urgency(id: int, urgent: bool): string {
    return JSON.stringify({ "WorkspaceUrgencyChanged": { "id": id, "urgent": urgent } });
  }
}
