"""Wrapper-delegation regressions (dol#83 / redisdol#3), run against fakeredis."""

import pytest
from fakeredis import FakeRedis
from dol import KeyCodecs, wrap_kvs

from redisdol import (
    RedisBytesPersister,
    RedisList,
    RedisPersister,
    store_from_source,
    store_from_sourced_object,
)
from redisdol.base import RedisCollection


def _store(cls=RedisPersister, server=None):
    return store_from_source(FakeRedis(server=server), cls)


def test_stores_do_not_expose_leaf_bound_factories():
    # A classmethod on the store surface is re-exported leaf-bound by every dol wrapper
    for cls in (RedisBytesPersister, RedisCollection, RedisPersister):
        assert not hasattr(cls, "from_source")
        assert not hasattr(cls, "from_sourced_object")
    W = KeyCodecs.prefixed("p:")(RedisPersister)
    assert not hasattr(W, "from_sourced_object")


def test_module_level_factories_give_plain_full_keyspace_store():
    base = _store()
    base["other"] = "x"
    f = store_from_sourced_object(base)
    assert type(f) is RedisPersister and f._source is base._source
    assert list(f) == [b"other"]
    g = store_from_source(base._source, RedisBytesPersister)
    assert type(g) is RedisBytesPersister


def test_wrapped_store_scoping_is_not_escapable(monkeypatch):
    monkeypatch.setattr("redisdol.base.Redis", FakeRedis)
    W = KeyCodecs.prefixed("p:")(RedisPersister)
    w = W(decode_responses=True)  # str keys, so the str prefix codec applies
    w["mine"] = "x"
    w.store._source.set("p:also", "y")
    assert sorted(w) == ["also", "mine"]
    # the wrapped class has no way to rebuild an unscoped sibling over the same keyspace
    assert not hasattr(w, "from_sourced_object")


def test_redislist_raw_by_default():
    s = _store()
    s["k"] = ["a", "b"]
    rl = s["k"]
    assert isinstance(rl, RedisList)
    rl.append("c")
    rl.extend(["d"])
    assert list(s["k"]) == [b"a", b"b", b"c", b"d"]


def test_redislist_codec_applied_on_every_write_and_read():
    l = RedisList(FakeRedis(), "l", encode=str.upper, decode=bytes.decode)
    l.extend(["a", "b"])
    l.append("c")
    l[0] = "z"
    assert list(l) == ["Z", "B", "C"]
    assert l[1:3] == ["B", "C"]
    assert l._source.lrange("l", 0, -1) == [b"Z", b"B", b"C"]  # stored encoded


def test_redislist_append_creates_missing_list():
    l = RedisList(FakeRedis(), "brand_new")
    l.append("x")
    assert list(l) == [b"x"]


def test_redislist_extend_empty_is_noop():
    l = RedisList(FakeRedis(), "e")
    l.extend([])
    assert len(l) == 0


def test_store_hands_its_list_codec_to_the_handles_and_its_own_writes():
    class S(RedisPersister):
        list_encode = staticmethod(str.upper)
        list_decode = staticmethod(bytes.decode)

    s = _store(S)
    s["k"] = ["a", "b"]
    s["k"].append("c")
    assert s._source.lrange("k", 0, -1) == [b"A", b"B", b"C"]  # no mixed encodings
    assert list(s["k"]) == ["A", "B", "C"]


def test_plain_function_as_class_level_codec_is_not_bound_as_a_method():
    class S(RedisPersister):
        def list_encode(x):  # noqa: N805 -- deliberately a plain function
            return x.upper()

    s = _store(S)
    s["k"] = ["a"]
    s["k"].append("b")
    assert s._source.lrange("k", 0, -1) == [b"A", b"B"]


def test_value_wrap_over_store_still_works_for_strings(monkeypatch):
    monkeypatch.setattr("redisdol.base.Redis", FakeRedis)
    w = wrap_kvs(RedisPersister, obj_of_data=lambda d: d)()
    w["s"] = "v"
    assert w["s"] == b"v"


# -- Mapping contract: missing keys raise KeyError (redisdol#4) ---------------------


@pytest.mark.parametrize("cls", [RedisBytesPersister, RedisPersister])
def test_missing_key_raises_keyerror(cls):
    s = _store(cls)
    with pytest.raises(KeyError):
        s["absent"]
    assert s.get("absent", "DEFAULT") == "DEFAULT"
    assert "absent" not in s
    s["present"] = "v"
    assert s.get("present") == b"v"


def test_reader_missing_key_raises_keyerror():
    from redisdol.base import RedisBytesReader

    r = store_from_source(FakeRedis(), RedisBytesReader)
    with pytest.raises(KeyError):
        r["absent"]
    assert r.get("absent", 0) == 0


def test_dict_of_store_roundtrips():
    s = _store()
    s["a"] = "x"
    s["b"] = ["1", "2"]
    d = dict(s)
    assert d[b"a"] == b"x" and list(d[b"b"]) == [b"1", b"2"]


# -- RedisStoreWithNumericLists passes non-lists through (redisdol#5) ----------------


def test_numeric_lists_store_passes_strings_through(monkeypatch):
    from redisdol.stores import RedisStoreWithNumericLists, _convert_numeric_list

    monkeypatch.setattr("redisdol.base.Redis", FakeRedis)
    s = RedisStoreWithNumericLists()
    s["str"] = "hello"
    s["nums"] = [1, -2, 3.5, "nope"]
    assert s["str"] == b"hello"
    assert s["nums"] == [1, -2, 3.5, b"nope"]
    assert dict(s) == {b"str": b"hello", b"nums": [1, -2, 3.5, b"nope"]}
    assert _convert_numeric_list("plain") == "plain"
