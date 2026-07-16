import pytest

from mcp_stateless_demo.cart.token import CartTokenCodec, InvalidToken


def test_roundtrip() -> None:
    codec = CartTokenCodec("secret")
    cart_id = "11111111-1111-1111-1111-111111111111"
    assert codec.decode(codec.encode(cart_id)) == cart_id


def test_tamper_detected() -> None:
    codec = CartTokenCodec("secret")
    token = codec.encode("abc")
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(InvalidToken):
        codec.decode(tampered)


def test_wrong_secret_rejected() -> None:
    token = CartTokenCodec("secret").encode("abc")
    with pytest.raises(InvalidToken):
        CartTokenCodec("other-secret").decode(token)


def test_malformed_rejected() -> None:
    with pytest.raises(InvalidToken):
        CartTokenCodec("secret").decode("no-signature-here")


def test_empty_secret_rejected() -> None:
    with pytest.raises(ValueError):
        CartTokenCodec("")
