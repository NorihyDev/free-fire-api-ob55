# Attribution and protocol provenance

This project is an unofficial community implementation, unaffiliated with Garena.

The original design reference requested for this project is
[0xMe/FreeFire-Api](https://github.com/0xMe/FreeFire-Api). It was inspected to understand
the guest authentication, encrypted protobuf requests, and player data endpoints.
Its application source and account credentials were not copied.

[WizkModz/TeeXezDevFFTCP](https://github.com/WizkModz/TeeXezDevFFTCP) was inspected
at the operator's request to compare authentication methods. Its source still
uses Garena guest token-grant or OAuth token-inspection before game login. No
executable code, credentials or TCP action implementation was copied. Our
direct-session mode is an independent implementation that reuses an operator-owned
game session. See `docs/sessions.md` for the exact distinction.

The six protobuf source files under `proto/` are redistributed from
[rifancorteza/ffapis](https://github.com/rifancorteza/ffapis), commit
`d7a71b4e4e9eb6826cc8649fdffa4302813ea1c8`, whose `package.json` and README declare
GPL-3.0. `MajorRegister.proto` has a `MajorRegister` package declaration added to avoid
global name collisions; the other five files are unchanged. Copyright remains with
the upstream contributors. `schemas.bin` is generated
from these files. This entire project is distributed under GPL-3.0-only.

Protocol constants (public game client identifiers, AES transport key/IV and endpoint
names) were cross-checked against those projects. They are protocol interoperability
values, not user account credentials. They can change independently of OB release names.
Never publish guest passwords, access tokens or session tokens.
