# jv-emoji-menu — PLAN H3b: emoji picker, the second "super-menu mode" (the
# same shape H3a's clipboard-history menu already established for H1's/H2's
# own dmenu popups).
#
# Unlike H3a there is no daemon half: an emoji is not a signal anything
# observes over time, it is a fixed table, so the whole feature is this one
# script. The table is a curated list baked in at build time rather than
# fetched — CLAUDE.md's privacy invariant already means every model here is
# local; the same "nothing this OS depends on reaches outside the machine at
# build or run time" reasoning extends to a keybind's own data, so this list
# ships in the derivation rather than as a network fetch this loop cannot
# review the far end of.
#
# `fuzzel --dmenu` (same themed popup H1/H2/H3a all reuse, `/etc/xdg/fuzzel/
# fuzzel.ini` via modules/theme.nix, no second palette) is handed one line
# per emoji, "<glyph> <name>", and returns the WHOLE selected line back on
# stdout — the glyph is never the first fuzzel decides to print alone. The
# picker then keeps only the text up to the first space (`${choice%% *}`,
# the analogue of H3a's `cliphist decode` step, except there is nothing to
# decode: the glyph IS what fuzzel already has) and copies exactly that to
# the clipboard with `wl-copy` — Wayland-only like every other surface in
# this repo (CLAUDE.md: "Wayland only, never X11-first"), never `xclip`/
# `xsel`, and never a synthetic keystroke (`wtype`/`ydotool`): invariant 3
# reserves injecting input for `jv-act` alone, and a themed dmenu plus a
# clipboard write is the same "two deliberate human steps, no jv-act
# capability needed" tier H2's own comment already argues for a destructive
# menu, let alone a copy.
#
# NO SECOND CONFIRMATION DIALOG, same reasoning as H2/H3a: opening the menu
# and picking an entry are already two deliberate steps, and copying a glyph
# to the clipboard is not destructive. Cancelling (Escape) is fuzzel exiting
# non-zero with nothing on stdout, turned into a clean no-op by `|| exit 0`;
# an empty selection (nothing typed, nothing matched) is caught explicitly
# since fuzzel can exit 0 with an empty line rather than non-zero — the same
# case H3a's own suite checks for cliphist.
{
  writeShellApplication,
  fuzzel,
  wl-clipboard,
}:
writeShellApplication {
  name = "jv-emoji-menu";

  runtimeInputs = [
    fuzzel
    wl-clipboard
  ];

  text = ''
    choice=$(printf '%s\n' \
      "😀 grinning face" \
      "😃 grinning face with big eyes" \
      "😄 grinning face with smiling eyes" \
      "😁 beaming face with smiling eyes" \
      "😆 grinning squinting face" \
      "😅 grinning face with sweat" \
      "🤣 rolling on the floor laughing" \
      "😂 face with tears of joy" \
      "🙂 slightly smiling face" \
      "🙃 upside-down face" \
      "😉 winking face" \
      "😊 smiling face with smiling eyes" \
      "😇 smiling face with halo" \
      "🥰 smiling face with hearts" \
      "😍 heart eyes" \
      "😘 face blowing a kiss" \
      "😜 winking face with tongue" \
      "🤔 thinking face" \
      "😐 neutral face" \
      "😴 sleeping face" \
      "👍 thumbs up" \
      "👎 thumbs down" \
      "👋 waving hand" \
      "🙌 raising hands" \
      "👏 clapping hands" \
      "🙏 folded hands" \
      "🤝 handshake" \
      "✌️ victory hand" \
      "🤞 crossed fingers" \
      "👌 ok hand" \
      "💪 flexed biceps" \
      "🤷 shrug" \
      "🫡 saluting face" \
      "👀 eyes" \
      "❤️ red heart" \
      "🧡 orange heart" \
      "💛 yellow heart" \
      "💚 green heart" \
      "💙 blue heart" \
      "💜 purple heart" \
      "🖤 black heart" \
      "🤍 white heart" \
      "💔 broken heart" \
      "💕 two hearts" \
      "🐶 dog face" \
      "🐱 cat face" \
      "🦊 fox" \
      "🐻 bear" \
      "🐼 panda" \
      "🐸 frog" \
      "🐵 monkey face" \
      "🦄 unicorn" \
      "🐝 honeybee" \
      "🦋 butterfly" \
      "🌸 cherry blossom" \
      "🌻 sunflower" \
      "🌈 rainbow" \
      "🔥 fire" \
      "⭐ star" \
      "🍕 pizza" \
      "🍔 hamburger" \
      "🍟 french fries" \
      "🌮 taco" \
      "🍣 sushi" \
      "🍩 doughnut" \
      "🍪 cookie" \
      "🎂 birthday cake" \
      "🍎 red apple" \
      "🍌 banana" \
      "☕ hot beverage" \
      "🍺 beer mug" \
      "🍷 wine glass" \
      "🍦 soft ice cream" \
      "🍫 chocolate bar" \
      "⚽ soccer ball" \
      "🏀 basketball" \
      "🎮 video game" \
      "🎧 headphone" \
      "🎸 guitar" \
      "🎉 party popper" \
      "🎁 wrapped gift" \
      "📱 mobile phone" \
      "💻 laptop" \
      "⌚ watch" \
      "📷 camera" \
      "🔑 key" \
      "💡 light bulb" \
      "📌 pushpin" \
      "✅ check mark" \
      "🚗 automobile" \
      "✈️ airplane" \
      "🚀 rocket" \
      "🏠 house" \
      "🌍 globe showing europe-africa" \
      "🗺️ world map" \
      "⛰️ mountain" \
      "🏖️ beach with umbrella" \
      "🌙 crescent moon" \
      "☀️ sun" \
      "✨ sparkles" \
      "💯 hundred points" \
      "❗ exclamation mark" \
      "❓ question mark" \
      "♻️ recycling symbol" \
      "⚡ high voltage" \
      "🔒 locked" \
      "🔓 unlocked" \
      "⏰ alarm clock" \
      "🎯 direct hit" \
      | fuzzel --dmenu --prompt "Emoji:  ") || exit 0
    [ -z "$choice" ] && exit 0
    printf '%s' "''${choice%% *}" | wl-copy
  '';

  meta = {
    description = "Emoji picker over a curated table (PLAN H3b)";
    mainProgram = "jv-emoji-menu";
  };
}
