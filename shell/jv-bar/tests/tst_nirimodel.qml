// NiriModel — what the bar believes the compositor has said (PLAN D1).
//
// The bar's ONE claim is "these are your workspaces, and this is the one
// your keyboard is in". Everything that can go wrong with it is a way of
// making that claim when it is not true any more:
//
//   · drawing workspaces from a compositor the bar has lost. niri's event
//     stream is a child process; when it dies the last snapshot is a
//     photograph of a desk that has since been rearranged, and a bar
//     showing yesterday's workspaces is worse than a bar showing none.
//   · inventing a workspace. Every delta niri sends names a workspace by
//     id, and an id the bar has never seen in a snapshot is a workspace
//     the bar knows nothing else about — not its output, not its index.
//     Acting on one would put a numberless pip on some arbitrary monitor.
//   · activating across outputs. Each output has exactly one active
//     workspace and niri's WorkspaceActivated says nothing about which
//     output it happened on — the model has to look that up, and a model
//     that deactivated every workspace everywhere would blank the two
//     monitors you did not touch.
//   · keeping the focus pip on a workspace that has been scrolled away
//     from. `focused: false` means "activated somewhere that does not have
//     the keyboard" and leaves the old focus alone — which is correct
//     UNLESS the old focus was on the very output that just moved.
//   · reading a line in a shape niri does not use. This is the one that no
//     test written from memory catches, so the snapshot below is not
//     written from memory: it is `harness/fixtures/niri/ares-desk.jsonl`,
//     line 1, byte for byte, recorded from the running compositor. A tools
//     test fails if this copy and that recording ever disagree.
//
// Headless, like every core/ file: NiriModel is pure QtQuick, driven with
// exactly the lines `niri msg --json event-stream` writes.
import QtQuick
import QtTest
import "../core"

TestCase {
  id: suite
  name: "NiriModel"

  // ---------------------------------------------------------------- real
  //
  // harness/fixtures/niri/ares-desk.jsonl line 1, verbatim: ares' three
  // monitors as niri described them. Note what it happens to contain — the
  // workspaces arrive in the order 2, 3, 4, 1, so HDMI-A-1's second
  // workspace is listed BEFORE its first. A model that trusted niri's
  // order would draw this desk's pips as "2 1".
  readonly property string snapshot: '{"WorkspacesChanged":{"workspaces":[{"id":2,"idx":1,"name":null,"output":"DP-1","is_urgent":false,"is_active":true,"is_focused":false,"active_window_id":null},{"id":3,"idx":1,"name":null,"output":"DP-2","is_urgent":false,"is_active":true,"is_focused":false,"active_window_id":null},{"id":4,"idx":2,"name":null,"output":"HDMI-A-1","is_urgent":false,"is_active":false,"is_focused":false,"active_window_id":null},{"id":1,"idx":1,"name":null,"output":"HDMI-A-1","is_urgent":false,"is_active":true,"is_focused":true,"active_window_id":2}]}}'

  // The other five lines of that recording, also verbatim, shortened only
  // where a window title would have put this machine's file paths in a
  // test. Every one of them is an event the bar does not read, and the
  // point of having them is that "does not read" is a behaviour worth
  // failing on rather than an omission.
  readonly property var unread: [
    '{"WindowsChanged":{"windows":[{"id":5,"title":"a terminal","app_id":"Alacritty","pid":770193,"workspace_id":1,"is_focused":false,"is_floating":false,"is_urgent":false}]}}',
    '{"KeyboardLayoutsChanged":{"keyboard_layouts":{"names":["English (US)"],"current_idx":0}}}',
    '{"OverviewOpenedOrClosed":{"is_open":false}}',
    '{"ConfigLoaded":{"failed":false}}',
    '{"CastsChanged":{"casts":[]}}'
  ]

  Component {
    id: niriModel
    NiriModel {}
  }

  // createObject() is typed QObject, so every member read on the result
  // would be `missing-property` to qmllint. Going through an untyped
  // helper keeps the file lint-clean at -W 0 (the HUD's tests do the same).
  function spawn(component) {
    const o = component.createObject(suite);
    verify(o, "failed to instantiate a test object");
    return o;
  }

  // A model that has seen the real desk.
  function live() {
    const m = spawn(niriModel);
    m.ingest(suite.snapshot);
    return m;
  }

  function labels(model, output) {
    return model.workspacesOn(output).map(w => w.label).join(" ");
  }

  function ids(model, output) {
    return model.workspacesOn(output).map(w => w.id).join(" ");
  }

  function byId(model, id) {
    const hit = model.workspaces.filter(w => w.id === id);
    compare(hit.length, 1, "expected exactly one workspace with id " + id);
    return hit[0];
  }

  // --- nothing heard yet ------------------------------------------------

  function test_knows_nothing_before_the_stream_says_anything() {
    const m = spawn(niriModel);
    verify(!m.linkUp, "the link cannot be up before niri has said a word");
    compare(m.workspaces.length, 0);
    // Not an empty desk — an unknown one. The strip draws nothing either
    // way, which is the point: no pip is honest, one pip is a guess.
    compare(m.workspacesOn("HDMI-A-1").length, 0);
  }

  function test_an_output_nobody_mentioned_has_no_workspaces() {
    compare(suite.live().workspacesOn("DP-9").length, 0);
  }

  // --- the recorded snapshot -------------------------------------------

  function test_the_recorded_snapshot_is_the_desk_it_was_recorded_from() {
    const m = suite.live();
    verify(m.linkUp, "a snapshot IS the link: niri has described the desk");
    compare(m.workspaces.length, 4);
    // Three outputs, and each one's own workspaces — never the whole list.
    compare(suite.ids(m, "HDMI-A-1"), "1 4");
    compare(suite.ids(m, "DP-1"), "2");
    compare(suite.ids(m, "DP-2"), "3");
  }

  function test_the_pips_are_in_nirisorder_by_index_not_arrival() {
    // The recording lists HDMI-A-1's idx 2 first. "1 2" is the desk; "2 1"
    // is the order the socket happened to use.
    compare(suite.labels(suite.live(), "HDMI-A-1"), "1 2");
  }

  function test_one_workspace_is_active_per_output_and_one_is_focused() {
    const m = suite.live();
    compare(m.workspaces.filter(w => w.focused).length, 1);
    verify(suite.byId(m, 1).focused, "HDMI-A-1's first workspace had the keyboard");
    for (const output of ["HDMI-A-1", "DP-1", "DP-2"])
      compare(m.workspacesOn(output).filter(w => w.active).length, 1, output);
    // Active is not focused: the other two monitors each have an active
    // workspace and neither of them has your keyboard.
    verify(suite.byId(m, 2).active && !suite.byId(m, 2).focused);
  }

  function test_an_unnamed_workspace_is_labelled_by_its_index() {
    // Every workspace in the recording has `name: null` — niri sends the
    // key and leaves it empty — so the label is the index, as a string.
    compare(suite.byId(suite.live(), 4).label, "2");
  }

  function test_a_named_workspace_is_labelled_by_its_name() {
    const m = spawn(niriModel);
    m.ingest(JSON.stringify({
      "WorkspacesChanged": {
        "workspaces": [{
          "id": 7,
          "idx": 1,
          "name": "brain",
          "output": "HDMI-A-1",
          "is_urgent": false,
          "is_active": true,
          "is_focused": true,
          "active_window_id": null
        }]
      }
    }));
    compare(suite.labels(m, "HDMI-A-1"), "brain");
  }

  // --- the lines the bar does not act on --------------------------------

  function test_the_other_five_recorded_events_change_nothing() {
    const m = suite.live();
    const before = JSON.stringify(m.workspaces);
    for (const line of suite.unread)
      m.ingest(line);
    compare(JSON.stringify(m.workspaces), before);
    verify(m.linkUp, "an unread event is not a dropped link");
  }

  function test_a_line_that_is_not_json_changes_nothing() {
    const m = suite.live();
    const before = JSON.stringify(m.workspaces);
    m.ingest("niri: error: could not connect to the socket");
    m.ingest("");
    m.ingest("{");
    compare(JSON.stringify(m.workspaces), before);
    verify(m.linkUp);
  }

  function test_json_that_is_not_an_event_changes_nothing() {
    const m = suite.live();
    const before = JSON.stringify(m.workspaces);
    // A bare value, a two-key object (no niri event has two), and an event
    // whose body is not an object. Every one of them parses.
    m.ingest("42");
    m.ingest('{"WorkspacesChanged":{"workspaces":[]},"ConfigLoaded":{"failed":false}}');
    m.ingest('{"WorkspacesChanged":7}');
    compare(JSON.stringify(m.workspaces), before);
  }

  function test_a_snapshot_that_is_not_a_list_of_workspaces_changes_nothing() {
    const m = suite.live();
    const before = JSON.stringify(m.workspaces);
    m.ingest('{"WorkspacesChanged":{"workspace":[]}}');
    m.ingest('{"WorkspacesChanged":{"workspaces":{}}}');
    // …and a workspace with nothing to draw it by is dropped, not defaulted
    // onto output "" at index 0.
    m.ingest('{"WorkspacesChanged":{"workspaces":[{"id":1}]}}');
    compare(JSON.stringify(m.workspaces), before);
  }

  // --- the deltas -------------------------------------------------------

  function test_activating_a_workspace_moves_the_active_one_on_its_output() {
    const m = suite.live();
    m.ingest('{"WorkspaceActivated":{"id":4,"focused":true}}');
    verify(suite.byId(m, 4).active, "the workspace niri activated is active");
    verify(!suite.byId(m, 1).active, "its output's previous one is not");
    // The other two monitors did not move.
    verify(suite.byId(m, 2).active && suite.byId(m, 3).active);
  }

  function test_activating_with_focus_moves_the_keyboard_and_only_it() {
    const m = suite.live();
    m.ingest('{"WorkspaceActivated":{"id":4,"focused":true}}');
    compare(m.workspaces.filter(w => w.focused).length, 1);
    verify(suite.byId(m, 4).focused);
  }

  function test_activating_without_focus_leaves_the_keyboard_where_it_was() {
    const m = suite.live();
    // DP-1 gets a second workspace, then it is activated from elsewhere —
    // a window moved to it, say. Your keyboard never left HDMI-A-1.
    m.ingest(JSON.stringify({
      "WorkspacesChanged": {
        "workspaces": [
          { "id": 1, "idx": 1, "name": null, "output": "HDMI-A-1", "is_urgent": false, "is_active": true, "is_focused": true, "active_window_id": 2 },
          { "id": 2, "idx": 1, "name": null, "output": "DP-1", "is_urgent": false, "is_active": true, "is_focused": false, "active_window_id": null },
          { "id": 9, "idx": 2, "name": null, "output": "DP-1", "is_urgent": false, "is_active": false, "is_focused": false, "active_window_id": null }
        ]
      }
    }));
    m.ingest('{"WorkspaceActivated":{"id":9,"focused":false}}');
    verify(suite.byId(m, 9).active, "DP-1 moved");
    verify(!suite.byId(m, 9).focused, "…without taking the keyboard");
    verify(suite.byId(m, 1).focused, "…which is still on HDMI-A-1");
  }

  function test_the_focus_pip_cannot_outlive_the_workspace_it_is_on() {
    const m = suite.live();
    // HDMI-A-1 scrolls to its second workspace, and niri reports it as an
    // activation WITHOUT focus. Whatever that means for the keyboard, the
    // workspace that had the pip is not on screen any more — so the bar
    // stops claiming it. Drawing focus on a workspace that is not even
    // active is the one state no desk can be in.
    m.ingest('{"WorkspaceActivated":{"id":4,"focused":false}}');
    verify(suite.byId(m, 4).active);
    compare(m.workspaces.filter(w => w.focused).length, 0);
  }

  function test_an_activation_of_a_workspace_nobody_has_heard_of_is_dropped() {
    const m = suite.live();
    const before = JSON.stringify(m.workspaces);
    m.ingest('{"WorkspaceActivated":{"id":404,"focused":true}}');
    compare(JSON.stringify(m.workspaces), before);
    compare(m.workspaces.length, 4, "no phantom workspace was created");
  }

  function test_an_activation_without_the_two_fields_is_dropped() {
    const m = suite.live();
    const before = JSON.stringify(m.workspaces);
    m.ingest('{"WorkspaceActivated":{"id":4}}');
    m.ingest('{"WorkspaceActivated":{"focused":true}}');
    m.ingest('{"WorkspaceActivated":{"id":"4","focused":true}}');
    compare(JSON.stringify(m.workspaces), before);
  }

  // --- urgency ----------------------------------------------------------

  function test_urgency_arrives_and_leaves_on_its_own_event() {
    const m = suite.live();
    verify(!suite.byId(m, 3).urgent);
    m.ingest('{"WorkspaceUrgencyChanged":{"id":3,"urgent":true}}');
    verify(suite.byId(m, 3).urgent, "a window on DP-2 is asking for you");
    // …and nothing else moved: urgency is a window asking, not a desk
    // rearranging. The keyboard stays where it was and DP-2's workspace
    // was already the active one there.
    verify(suite.byId(m, 1).focused, "the keyboard did not move");
    verify(suite.byId(m, 3).active, "DP-2's active workspace did not change");
    verify(!suite.byId(m, 3).focused, "and urgency never takes the keyboard");
    m.ingest('{"WorkspaceUrgencyChanged":{"id":3,"urgent":false}}');
    verify(!suite.byId(m, 3).urgent);
  }

  function test_urgency_already_true_in_the_snapshot_is_carried_in() {
    // Found by mutation, once PLAN D11 let this suite be graded at all:
    // every fixture here sends `is_urgent: false`, so `raw.is_urgent === true`
    // could be the literal `false` and the whole suite stayed green. It is
    // not a hypothetical branch — the snapshot is what the bar gets when it
    // STARTS, and `WorkspacesChanged` arrives again whenever the set of
    // workspaces changes, so a window that went urgent before either moment
    // is only ever announced this way. Drawn calm, it is a message missed.
    const m = suite.live();
    m.ingest(JSON.stringify({
      "WorkspacesChanged": {
        "workspaces": [
          { "id": 1, "idx": 1, "name": null, "output": "HDMI-A-1", "is_urgent": false, "is_active": true, "is_focused": true, "active_window_id": 2 },
          { "id": 3, "idx": 1, "name": null, "output": "DP-2", "is_urgent": true, "is_active": true, "is_focused": false, "active_window_id": null }
        ]
      }
    }));
    verify(suite.byId(m, 3).urgent, "it was already asking when we connected");
    verify(!suite.byId(m, 1).urgent, "and the one that was not, is not");
  }

  function test_urgency_for_an_unknown_workspace_is_dropped() {
    const m = suite.live();
    const before = JSON.stringify(m.workspaces);
    m.ingest('{"WorkspaceUrgencyChanged":{"id":404,"urgent":true}}');
    m.ingest('{"WorkspaceUrgencyChanged":{"id":3,"urgent":"yes"}}');
    compare(JSON.stringify(m.workspaces), before);
  }

  // --- workspaces coming and going -------------------------------------

  function test_a_second_snapshot_replaces_the_desk_wholesale() {
    const m = suite.live();
    // niri's workspaces are dynamic: close the last window on one and it
    // stops existing. A model that merged snapshots would keep drawing it.
    m.ingest(JSON.stringify({
      "WorkspacesChanged": {
        "workspaces": [
          { "id": 1, "idx": 1, "name": null, "output": "HDMI-A-1", "is_urgent": false, "is_active": true, "is_focused": true, "active_window_id": 2 }
        ]
      }
    }));
    compare(m.workspaces.length, 1);
    compare(m.workspacesOn("DP-1").length, 0, "DP-1's workspace is gone");
  }

  // --- the link ---------------------------------------------------------

  function test_a_lost_stream_takes_the_workspaces_with_it() {
    const m = suite.live();
    m.applyLink(false, "niri stopped");
    verify(!m.linkUp);
    compare(m.workspaces.length, 0, "the desk is unknown, not empty");
    compare(m.linkError, "niri stopped");
  }

  function test_the_stream_coming_back_is_not_the_desk_coming_back() {
    const m = suite.live();
    m.applyLink(false, "niri stopped");
    m.applyLink(true, "");
    // A running child process is not knowledge. Only a snapshot is, and
    // niri sends one the moment it accepts the connection.
    verify(!m.linkUp, "the link is the snapshot, not the process");
    compare(m.workspaces.length, 0);
    m.ingest(suite.snapshot);
    verify(m.linkUp);
    compare(m.workspaces.length, 4);
  }
}
