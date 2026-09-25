// NiriModel — what the bar believes the compositor has said (PLAN D1).
//
// This is the half of the bar's niri link that is pure QtQuick: parse a
// line, update the desk, answer questions about it. `Niri.qml` wraps it
// with the Quickshell half — the `niri msg --json event-stream` child and
// the respawn timer — which cannot be loaded outside the quickshell
// binary. Splitting them is what makes this testable headlessly, exactly
// as `core/BusModel.qml` splits the HUD's bus link.
//
// The rules the strip rides on, and the reason each one is a rule:
//
//   · `linkUp` is the SNAPSHOT, not the process. niri sends a
//     `WorkspacesChanged` the moment it accepts a connection, so until
//     that line arrives the honest answer about the desk is "I don't
//     know" — a running child process is not knowledge.
//   · when the stream drops, the desk is emptied. The last snapshot is a
//     photograph, and a bar drawing workspaces that were rearranged three
//     minutes ago is lying in exactly the way invariant 10 is about.
//   · nothing is ever invented. A delta about an id no snapshot mentioned
//     is dropped whole, because the bar knows nothing else about that
//     workspace — not its output, not its index, not what to draw.
//   · a snapshot is taken whole or not at all. One unreadable workspace in
//     the list means the list is not the shape this model was written for,
//     and half a desk drawn confidently is worse than the previous desk.
//   · focus implies active. niri's `WorkspaceActivated { id, focused }`
//     leaves the focus alone when `focused` is false — right, unless the
//     workspace that HAD the focus is the one just scrolled off. A pip on
//     a workspace that is not even on its monitor is a state no desk can
//     be in, so it is not one this model can be in either.
//
// What it deliberately does NOT know: which workspaces have windows on
// them. `WorkspaceActiveWindowChanged` is the event that would say so and
// nothing here has ever seen one fire (see harness/fixtures/niri/README.md
// — the recording is a connect snapshot, and recording a delta means
// rearranging a desk someone is sitting at). An occupancy pip drawn from
// an event that might not arrive is a pip that goes stale silently, which
// is the one failure mode a bar must not have. PLAN D12.
import QtQuick

QtObject {
  id: root

  // True only once niri has described the desk. Every element must gate
  // its content on this.
  property bool linkUp: false
  // Why the desk is unknown, for the log. Never rendered as a state of the
  // machine — it describes the pipe, not the compositor.
  property string linkError: "starting"
  // Every workspace on every output, in niri's own order. Replaced
  // wholesale (never mutated in place) so bindings actually re-evaluate.
  // Each entry: { id, idx, output, name, label, active, focused, urgent }.
  property var workspaces: []

  // The workspaces on one output, in the order they are laid out — which
  // is `idx`, and is NOT the order niri lists them in. An output nobody
  // mentioned has none, the same answer an unknown desk gives, because
  // both are "nothing true to draw".
  function workspacesOn(output: string): var {
    return root.workspaces.filter(w => w.output === output).sort((a, b) => a.idx - b.idx);
  }

  // The stream's own state, from the process that runs it. `up` true is
  // NOT enough to make `linkUp` true: only a snapshot is (see above).
  function applyLink(up: bool, err: string): void {
    root.linkError = err;
    if (up)
      return;
    root.linkUp = false;
    root.workspaces = [];
  }

  // One line of `niri msg --json event-stream`.
  function ingest(line: string): void {
    if (line.length === 0)
      return;
    let msg = null;
    try {
      msg = JSON.parse(line);
    } catch (e) {
      // A line the bar cannot parse is a line the bar does not act on.
      // niri writes its own errors to stderr, so this is genuinely
      // unexpected rather than the ordinary way a failure arrives.
      console.warn("jv-bar: unparseable niri line dropped");
      return;
    }
    if (!msg || typeof msg !== "object" || Array.isArray(msg))
      return;
    // Every niri event is a one-key object — the serde externally-tagged
    // enum. Two keys is not an event this model understands the shape of.
    const kinds = Object.keys(msg);
    if (kinds.length !== 1)
      return;
    const kind = kinds[0];
    const body = msg[kind];
    if (!body || typeof body !== "object" || Array.isArray(body))
      return;

    if (kind === "WorkspacesChanged") {
      root.applySnapshot(body.workspaces);
      return;
    }
    if (kind === "WorkspaceActivated") {
      root.applyActivated(body.id, body.focused);
      return;
    }
    if (kind === "WorkspaceUrgencyChanged") {
      root.applyUrgency(body.id, body.urgent);
      return;
    }
    // Everything else niri says is about windows, layouts, the overview,
    // screencasts or its own config. The bar reads none of it.
  }

  // --- the events, one function each -------------------------------------

  // The whole desk, replacing whatever was there. Dynamic workspaces means
  // this arrives whenever one is created or destroyed, so a MERGE would
  // keep drawing a workspace that has stopped existing.
  function applySnapshot(list: var): void {
    if (!Array.isArray(list))
      return;
    let next = [];
    for (const raw of list) {
      const w = root.readWorkspace(raw);
      if (w === null) {
        // Taken whole or not at all: a list this model can only partly
        // read is not the shape it was written for, and the safe half of
        // a wrong answer is still a wrong answer.
        console.warn("jv-bar: a niri workspace snapshot was unreadable; kept the old desk");
        return;
      }
      next.push(w);
    }
    root.workspaces = next;
    root.linkUp = true;
  }

  // `WorkspaceActivated { id, focused }` — the workspace became the active
  // one ON ITS OWN OUTPUT, which the event does not say and this has to
  // look up. Deactivating every workspace everywhere would blank the two
  // monitors you did not touch.
  function applyActivated(id: var, focused: var): void {
    if (typeof id !== "number" || typeof focused !== "boolean")
      return;
    const target = root.find(id);
    if (target === null)
      return;
    root.workspaces = root.workspaces.map(w => {
      const active = w.output === target.output ? w.id === id : w.active;
      // Focus moves only when niri says it did; what it cannot do is stay
      // on a workspace that is no longer on its monitor.
      const keeps = focused ? w.id === id : w.focused;
      return root.patched(w, { "active": active, "focused": keeps && active });
    });
  }

  // `WorkspaceUrgencyChanged { id, urgent }` — a window on that workspace
  // is asking for you. It is not attention and never moves the keyboard.
  function applyUrgency(id: var, urgent: var): void {
    if (typeof id !== "number" || typeof urgent !== "boolean")
      return;
    if (root.find(id) === null)
      return;
    root.workspaces = root.workspaces.map(w => w.id === id ? root.patched(w, { "urgent": urgent }) : w);
  }

  // --- the small pieces ---------------------------------------------------

  // One workspace as niri sends it, or null if it is not one. The three
  // required fields are the three the strip cannot draw without: which
  // workspace this is, where it is, and where in the row it goes.
  function readWorkspace(raw: var): var {
    if (!raw || typeof raw !== "object")
      return null;
    if (typeof raw.id !== "number" || typeof raw.idx !== "number")
      return null;
    if (typeof raw.output !== "string" || raw.output.length === 0)
      return null;
    // niri sends `name: null` for the ordinary unnamed workspace and the
    // string for a named one; the label is the one the user would say.
    const name = typeof raw.name === "string" && raw.name.length > 0 ? raw.name : "";
    return {
      "id": raw.id,
      "idx": raw.idx,
      "output": raw.output,
      "name": name,
      "label": name.length > 0 ? name : String(raw.idx),
      "active": raw.is_active === true,
      "focused": raw.is_focused === true,
      "urgent": raw.is_urgent === true
    };
  }

  function find(id: int): var {
    const hit = root.workspaces.filter(w => w.id === id);
    return hit.length === 1 ? hit[0] : null;
  }

  // A copy of one workspace with some fields replaced. Copies, because a
  // list mutated in place is a list QML's bindings never hear about.
  function patched(w: var, changes: var): var {
    let out = {};
    for (const key in w)
      out[key] = w[key];
    for (const key in changes)
      out[key] = changes[key];
    return out;
  }
}
