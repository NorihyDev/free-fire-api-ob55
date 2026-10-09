from importlib.resources import files

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf import descriptor_pb2, descriptor_pool, json_format, message_factory
from google.protobuf.message import DecodeError

from freefire_api.errors import APIError

_pool = descriptor_pool.DescriptorPool()
_set = descriptor_pb2.FileDescriptorSet()
_set.ParseFromString(files("freefire_api.protocol").joinpath("schemas.bin").read_bytes())
for _file in _set.file:
    _pool.Add(_file)


def message_type(schema: str, direction: str):
    return message_factory.GetMessageClass(_pool.FindMessageTypeByName(f"{schema}.{direction}"))


def encode(schema: str, data: dict, key: bytes, iv: bytes) -> bytes:
    message = message_type(schema, "request")()
    json_format.ParseDict(data, message)
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(message.SerializeToString(), 16))


def decode(schema: str, body: bytes) -> dict:
    if not body:
        raise APIError(502, "UPSTREAM_EMPTY_RESPONSE", "Game server returned an empty response.")
    message = message_type(schema, "response")()
    try:
        message.ParseFromString(body)
    except DecodeError as exc:
        raise APIError(
            502, "UPSTREAM_PROTOCOL_ERROR", "Game response could not be decoded; check protocol version."
        ) from exc
    return json_format.MessageToDict(message, preserving_proto_field_name=True)
