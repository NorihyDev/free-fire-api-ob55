"""Regenerate the checked-in descriptor; no compiler is needed to run the API."""

from pathlib import Path

from grpc_tools import protoc

root = Path(__file__).resolve().parents[1]
names = [
    "MajorLogin",
    "MajorRegister",
    "PlayerPersonalShow",
    "SearchAccountByName",
    "PlayerStats",
    "PlayerCSStats",
]
result = protoc.main(
    [
        "protoc",
        f"-I{root / 'proto'}",
        f"--descriptor_set_out={root / 'freefire_api/protocol/schemas.bin'}",
        "--include_imports",
        *[str(root / "proto" / (name + ".proto")) for name in names],
    ]
)
raise SystemExit(result)
