# Input

- INT 9 handler (installed ~0x10E8B) maintains `g_keytable_live` 0x5E3D4 (256 B, index = scancode,
  |0x80 for E0-prefixed keys) [C].
- Each frame: copied to `g_keytable_frame` 0x5E4D4, then for local human players (kind 1):
  `key_flag[k] = keytable_frame[keybind[k]]` for k = thrust, fire2, left, right, fire1 [C].
  Player 1 defaults (KEYS.DAT): Up, Down, Left, Right, RShift.
- Remote players (kind 3): 5 flags packed `bits + 0x20` over serial (`serial_send_local_keys` 0x36840);
  local keys are delayed 2 frames (4 if 0x9AC28==1) through a 32-entry buffer so both machines apply the
  same inputs on the same frame [C] => lockstep.
- Computer players (kind 2): AI routine 0x73F0 [H] writes the same flags.
- Input is sampled once per tick at frame start [C] (resolves plan §3.4 [H]).
- Confusion status (`confuse_timer`/`confuse_kind`) permutes flags after sampling.
