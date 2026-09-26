// Probe — the second engine, for the half of every scene QtTest never shows
// anybody (PLAN D38).
//
// D36 made all three shot harnesses refuse a run whose QML threw, by reading
// the runner's own output back. What it cannot read is what the runner never
// prints, and qmltestrunner drops every message logged while no test function
// is running. Measured against Qt 6.11.1, with two drivers in one directory:
//
//     PASS   : qmltestrunner::Probea::cleanupTestCase()
//     QWARN  : qmltestrunner::UnknownTestFunc() qml: warn from b onCompleted
//     QWARN  : qmltestrunner::UnknownTestFunc() …/tst_b.qml:7: TypeError: …
//     PASS   : qmltestrunner::Probeb::initTestCase()
//
// — identical files, and only the SECOND one is heard. The first driver's
// scene is built before the run begins, where QtTest's handler drops
// everything; every later driver's is built between two test functions, where
// it does not. So which of a harness's surfaces is covered is decided by
// alphabetical order, and in all three harnesses the uncovered one is the
// first: `tst_fit`, `tst_settle`, `tst_settle`.
//
// This is the other half, and it is not a cleverer scan — it is a different
// engine. Plain `qml` installs no handler of its own, so the scene is loaded
// a second time and the engine's own messages reach stderr as the engine
// wrote them. `tools/qmlerrors.py` reads that output under the same rule it
// reads the runner's, because a throw is a throw and the discriminator was
// never the `QWARN :` in front of it.
//
// WHAT IT SEES: the scene the document next door declares, with every
// singleton in the state it is in before anything has been fed to it — which
// is the state the shell is in for the first frame of every session, and the
// one no shot on any sheet is a picture of.
//
// WHAT IT DOES NOT SEE: a delegate that does not exist. A `Repeater` with an
// empty model has no children, so a fault inside its delegate is out of reach
// here and in reach of D36, which drives real data through the real model
// inside a test body. The two halves are complements, not substitutes.
//
// AND WHAT IT DELIBERATELY DOES NOT DO. The first version of this file read
// every property of every object in the tree, on the theory that a QML
// binding is lazy and one nobody asks for never evaluates. That theory is
// wrong here, and the measurement says so: an injected `property int
// injected: root.desk.nothingHere.count` on the bar's strip, and the same
// fault as a `property var`, BOTH printed with the walk disabled and the
// census reading nothing. Bindings on a created object are evaluated as it is
// created. So the reads bought nothing, and 9,319 property reads that buy
// nothing are 9,319 property reads to explain. What is left is the census,
// which buys the one thing the run cannot otherwise claim: that a scene was
// really built here.
import QtQuick

Item {
  id: root

  // The scene to read, declared by the document that instantiates this one.
  // A property rather than the default child list because the census has to
  // start somewhere nameable, and "my first child" would silently start at a
  // Timer if anyone ever added one above it.
  property Item subject: null

  // The probe's box is the subject's. Nothing here is photographed, and a
  // size of its own would be one more declaration of a surface box that
  // already has too many (PLAN D33).
  width: root.subject ? root.subject.width : 0
  height: root.subject ? root.subject.height : 0

  // A containment tree cannot be a cycle, so this is a backstop and not a
  // rule — it bounds a census that a future QML type could make unbounded.
  readonly property int maxDepth: 24

  property int built: 0

  // How many objects the scene really built.
  //
  // `data` rather than `children`: it is an Item's default property, so it
  // holds the non-visual objects too — the Timer, the Connections, the
  // QtObject holding a model — and a scene is those as much as it is its
  // rectangles. A type that has no `data` (a plain QtObject) ends the count
  // there, which is honest: nothing can be reached through it.
  //
  // `node: var` and not `node: QtObject`, which is the one place in this repo
  // where the dynamically typed thing is the correct thing: the census is
  // generic over every type the tree can hold, and `data` is not a member of
  // QtObject — qmllint is right to refuse it on a typed parameter, and asking
  // an unknown object what it holds is the whole job here.
  function census(node: var, depth: int): void {
    if (!node || depth > root.maxDepth)
      return;
    root.built += 1;
    const held = node.data;
    if (held === undefined || held === null)
      return;
    for (let i = 0; i < held.length; i++)
      root.census(held[i], depth + 1);
  }

  // After a frame, not at completion: a scene whose first frame has not been
  // drawn has not had its geometry resolved, and a binding that throws on
  // re-evaluation throws when something changes rather than when it is made.
  // One interval past the first render under the offscreen platform is the
  // cheapest way to be after both.
  Timer {
    interval: 250
    running: true

    onTriggered: {
      root.census(root.subject, 0);
      console.log("qmlprobe: the scene built " + root.built + " objects");
      // A probe that counted nothing loaded nothing and proved nothing. That
      // is not a pass — it is the same silence this file exists to remove —
      // so it is the one thing here that sets a status itself.
      Qt.exit(root.built > 0 ? 0 : 3);
    }
  }
}
