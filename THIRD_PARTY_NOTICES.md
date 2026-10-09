# Attribution and protocol provenance

This project is an unofficial community implementation, unaffiliated with Garena.

The original design reference requested for this project is
[0xMe/FreeFire-Api](https://github.com/0xMe/FreeFire-Api). It was inspected to understand
the guest authentication, encrypted protobuf requests, and player data endpoints.
Its application source and account credentials were not copied.

The five protobuf source files under `proto/` are redistributed unchanged from
[rifancorteza/ffapis](https://github.com/rifancorteza/ffapis), commit
`d7a71b4e4e9eb6826cc8649fdffa4302813ea1c8`, whose `package.json` and README declare
GPL-3.0. Copyright remains with the upstream contributors. `schemas.bin` is generated
from these files. This entire project is distributed under GPL-3.0-only.

Protocol constants (public game client identifiers, AES transport key/IV and endpoint
names) were cross-checked against those projects. They are protocol interoperability
values, not user account credentials. They can change independently of OB release names.
Never publish guest passwords, access tokens or session tokens.
