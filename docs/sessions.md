# Live requests without Garena auth calls

Direct-session mode calls the regional game's player endpoints with a game JWT
you already own. It makes no requests to the guest token-grant endpoint,
token-inspection endpoint, MajorLogin, GetLoginData or TCP chat/online sockets.
This removes the API's login step; it does not remove the game server's requirement
for valid authenticated requests.

## What the requested repository actually does

[WizkModz/TeeXezDevFFTCP](https://github.com/WizkModz/TeeXezDevFFTCP) describes its flow
as guest authentication, MajorLogin, GetLoginData, then TCP connection. Its
[ReQAPI.py](https://github.com/WizkModz/TeeXezDevFFTCP/blob/main/teexez/ReQAPI.py) has:

- `auth_guest_token`: calls `auth.garena.com/oauth/guest/token/grant` with UID/password.
- `auth_token_inspect`: calls `auth.garena.com/oauth/token/inspect` for a supplied
  OAuth token to obtain the Open ID.
- `MajorLogin`: exchanges the access token for a game session and regional URL.
- `GetLoginData`: uses that authenticated game session to discover TCP addresses.

Both of its login paths still involve Garena authentication. A TCP socket does
not issue an anonymous game JWT. No credentials or executable code were copied
from that repository, and its bot was not run.

Our direct-session mode starts after those login steps, using an existing game
JWT and server URL. The REST profile, stats and search operations do not need
the bot's chat, invite, squad, or emote operations.

## Configure your own session

Set in `.env`:

```dotenv
FF_MODE=live
FF_AUTH_METHOD=session
FF_SESSIONS_FILE=config/sessions.json
```

Create private `config/sessions.json`:

```json
{
  "IND": {
    "token": "YOUR_OWN_GAME_SESSION_JWT",
    "server_url": "https://client.ind.freefiremobile.com"
  }
}
```

Use the exact game JWT and regional URL associated with your own existing session.
Remove the `Bearer ` prefix from the configured token. A Garena OAuth access token,
public player UID, Facebook password or Google password is not a game session JWT.
The API cannot generate a valid signed game JWT without account authentication.

JWT payload expiry is read only to avoid sending locally expired tokens. Claims
are not locally verified and do not authorize any REST caller. The game server
verifies the supplied bearer token. If a token has no readable integer `exp` claim,
add `expires_at` with its actual expiry time in Unix seconds.

Restart after changing the session file. Missing tokens return
`503 REGION_NOT_CONFIGURED`; expired tokens return `503 SESSION_EXPIRED` without a
network request. Upstream 401/403 returns `503 SESSION_REJECTED` after one player
request. There is no fallback to guest auth or demo mode.

## Current verification

As of October 9, 2026, no owned session token has been supplied, so live game
responses cannot be verified. Automated HTTP-transport tests prove that direct
session profile requests contact only `GetPlayerPersonalShow`, and that rejected
tokens do not trigger a login or retry. These are controlled tests, not live results.

The operator currently has no session token. The required next step for live
access is obtaining a valid session from an account they own, or using a player
data provider they are authorized to access. Previously documented public example
services were also checked: the Render example returned HTTP 404 and the old
Vercel example returned HTTP 401. Neither was adopted as a working provider.
