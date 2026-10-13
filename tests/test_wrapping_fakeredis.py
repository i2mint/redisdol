"""Wrapper-delegation regressions (dol#83 / redisdol#3), run against fakeredis."""

import pytest
from fakeredis import FakeRedis
from dol import KeyCodecs, Store, wrap_kvs

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


def test_decode_responses_connection_missing_and_present_keys():
    s = store_from_source(FakeRedis(decode_responses=True), RedisPersister)
    s["k"] = "v"
    s["l"] = ["a"]
    assert s["k"] == "v" and list(s["l"]) == ["a"]
    with pytest.raises(KeyError):
        s["absent"]


def test_unsupported_redis_type_raises_typeerror_not_none():
    s = _store()
    s._source.hset("h", "f", "v")
    assert "h" in s
    with pytest.raises(TypeError, match="hash"):
        s["h"]


# -- RedisList: MutableSequence contract (redisdol#6, #7) ----------------------------


def _rl(items=(), **kw):
    l = RedisList(FakeRedis(), "l", **kw)
    l.extend(items)
    return l


def _dec(l):
    return [bytes(x).decode() for x in l]


@pytest.mark.parametrize(
    "idx",
    [(None, None), (1, 0), (0, 0), (1, 3), (-2, None), (None, -1), (2, 99), (5, 9), (3, 1)],
)
def test_redislist_slices_match_python_list(idx):
    ref = list("abcd")
    l = _rl(ref)
    sl = slice(*idx)
    assert _dec(l[sl]) == ref[sl]


def test_redislist_stepped_slices_match_python_list():
    ref = list("abcdef")
    l = _rl(ref)
    for sl in (slice(None, None, 2), slice(None, None, -1), slice(1, 5, 2)):
        assert _dec(l[sl]) == ref[sl]


def test_redislist_index_errors():
    l = _rl("ab")
    assert l[-1] == b"b"
    for bad in (2, 99, -3):
        with pytest.raises(IndexError):
            l[bad]
        with pytest.raises(IndexError):
            l[bad] = "x"
        with pytest.raises(IndexError):
            del l[bad]
    with pytest.raises(IndexError):
        RedisList(FakeRedis(), "nokey")[0]
    assert _dec(l) == ["a", "b"]  # failed ops left it untouched


def test_redislist_index_and_contains_terminate():
    l = _rl("abc")
    assert l.index(b"c") == 2
    with pytest.raises(ValueError):
        l.index(b"absent")
    assert b"a" in l and b"z" not in l


def test_redislist_delitem_with_duplicates():
    l = _rl("abab")
    del l[2]
    assert _dec(l) == ["a", "b", "b"]
    del l[-1]
    assert _dec(l) == ["a", "b"]
    del l[0]
    assert _dec(l) == ["b"]
    del l[0]
    assert len(l) == 0


def test_redislist_insert_matches_python_list_including_duplicates():
    import random

    rnd = random.Random(0)
    for _ in range(50):
        ref = [rnd.choice("ab") for _ in range(rnd.randrange(0, 6))]
        l = _rl(ref)
        i = rnd.randrange(-8, 9)
        ref.insert(i, "X")
        l.insert(i, "X")
        assert _dec(l) == ref, (i,)


def test_redislist_insert_into_missing_list_and_codec():
    l = RedisList(FakeRedis(), "new", encode=str.upper, decode=bytes.decode)
    l.insert(0, "a")
    l.insert(0, "b")
    l.insert(1, "c")
    assert list(l) == ["B", "C", "A"]


def test_redislist_mutablesequence_mixins():
    l = _rl("abc")
    assert l.pop() == b"c"
    l.remove(b"a")
    assert _dec(l) == ["b"]
    l += [b"x", b"y"]
    l.reverse()
    assert _dec(l) == ["y", "x", "b"]
    l.clear()
    assert len(l) == 0 and not l._source.exists("l")


def test_redislist_iter_batches(monkeypatch):
    l = _rl([str(i) for i in range(25)])
    monkeypatch.setattr(RedisList, "iter_batch_size", 10)
    assert _dec(l) == [str(i) for i in range(25)]
    assert len(list(_rl([str(i) for i in range(20)]))) == 20


def test_redislist_slice_assign_and_delete_unsupported():
    l = _rl("abc")
    with pytest.raises(NotImplementedError):
        l[0:1] = ["x"]
    with pytest.raises(NotImplementedError):
        del l[0:1]


def test_store_assign_empty_list_keeps_existing_value():
    s = _store()
    s["k"] = ["a", "b"]
    with pytest.raises(ValueError):
        s["k"] = []
    assert list(s["k"]) == [b"a", b"b"]


def test_store_assign_replaces_list_and_accepts_generators_and_numbers():
    s = _store()
    s["k"] = ["a", "b"]
    s["k"] = (x for x in "xyz")
    assert list(s["k"]) == [b"x", b"y", b"z"]
    s["n"] = 42
    assert s["n"] == b"42"


def test_redislist_non_integer_index_is_typeerror(monkeypatch):
    l = _rl("ab")
    for bad in ("x", 1.5, None):
        with pytest.raises(TypeError):
            l[bad]
        with pytest.raises(TypeError):
            l[bad] = "v"
        with pytest.raises(TypeError):
            del l[bad]
        with pytest.raises(TypeError):
            l.insert(bad, "v")
    monkeypatch.setattr(RedisList, "iter_batch_size", 0)  # degenerate: still terminates
    assert _dec(l) == ["a", "b"]


# ---- store_from_source on dol-wrapped classes (i2mint/redisdol#10) ----------------------


def test_store_from_source_builds_wrapped_classes():
    from redisdol.stores import RedisStoreWithNumericLists

    r = FakeRedis()
    s = store_from_source(r, RedisStoreWithNumericLists)
    s["nums"] = [1, 2.5, "x"]
    assert s["nums"] == [1, 2.5, b"x"]  # the wrapper's codec is applied
    s["str"] = "hello"
    assert s["str"] == b"hello"
    assert isinstance(s, RedisStoreWithNumericLists)
    assert r.lrange("nums", 0, -1) == [b"1", b"2.5", b"x"]  # over the given connection


def test_store_from_source_builds_stacked_wrappers():
    from redisdol.stores import RedisStoreWithNumericLists

    r = FakeRedis()
    cls = KeyCodecs.prefixed("p:")(RedisStoreWithNumericLists)
    s = store_from_source(r, cls)
    s["k"] = [1, 2]
    assert r.lrange("p:k", 0, -1) == [b"1", b"2"] and s["k"] == [1, 2]


def test_store_from_source_refuses_wrapped_class_it_cannot_unwrap():
    from dol import Store

    class Opaque(Store):  # a Store subclass that is not a dol class-wrapper
        pass

    with pytest.raises(TypeError, match="can't be determined"):
        store_from_source(FakeRedis(), Opaque)


def test_store_from_source_runs_the_wrapper_classes_own_init():
    from dol import Store

    class Tagged(Store):
        def __init__(self, store, tag="T"):
            super().__init__(store)
            self.tag = tag

    cls = Tagged.wrap(RedisPersister)
    s = store_from_source(FakeRedis(), cls)
    assert s.tag == "T"
    s["k"] = "v"
    assert s["k"] == b"v"
    cls2 = wrap_kvs(RedisPersister, wrapper=Tagged, obj_of_data=lambda v: v)
    assert store_from_source(FakeRedis(), cls2).tag == "T"


# ---- wrong-type keys and bytes-like values (i2mint/redisdol#12) -------------------------


def test_list_ops_on_a_string_key_are_a_wrong_type_not_an_index_error():
    r = FakeRedis()
    r.set("s", "text")
    lst = RedisList(r, "s")
    with pytest.raises(TypeError, match="not a list"):
        lst[0] = "x"
    with pytest.raises(TypeError, match="not a list"):
        del lst[0]
    assert r.get("s") == b"text"  # untouched


def test_list_ops_out_of_range_or_missing_are_still_index_errors():
    r = FakeRedis()
    r.rpush("l", "a")
    lst = RedisList(r, "l")
    for op in (lambda: lst.__setitem__(5, "x"), lambda: lst.__delitem__(5)):
        with pytest.raises(IndexError):
            op()
    missing = RedisList(r, "nope")
    with pytest.raises(IndexError):
        missing[0] = "x"
    with pytest.raises(IndexError):
        del missing[0]


def test_other_redis_errors_are_not_disguised_as_index_errors():
    from redis.exceptions import ResponseError

    class Failing:
        def lset(self, *a):
            raise ResponseError("READONLY You can't write against a read only replica.")

    with pytest.raises(ResponseError, match="READONLY"):
        RedisList(Failing(), "l")[0] = "x"


@pytest.mark.parametrize("make", [bytearray, memoryview])
def test_bytes_like_values_are_stored_as_a_string_not_a_list_of_ints(make):
    s = _store()
    s["k"] = make(b"hello")
    assert s["k"] == b"hello"
    assert s._source.type("k") == b"string"


def test_key_names_do_not_change_how_a_pipeline_error_is_classified():
    from redis.exceptions import ResponseError

    r = FakeRedis()
    with pytest.raises(IndexError):  # a missing key that is *named* WRONGTYPE
        del RedisList(r, "WRONGTYPE")[0]

    class ReadOnlyPipe:  # a READONLY error on a key named like a list error
        def pipeline(self, transaction=True):
            class P:
                def __enter__(s):
                    return s

                def __exit__(s, *a):
                    return False

                def lset(s, *a):
                    pass

                def lrem(s, *a):
                    pass

                def execute(s):
                    raise ResponseError(
                        "Command # 1 (LSET no such key 0 x) of pipeline caused error: "
                        "READONLY You can't write against a read only replica."
                    )

            return P()

    with pytest.raises(ResponseError, match="READONLY") as info:
        del RedisList(ReadOnlyPipe(), "no such key")[0]
    assert info.value.__cause__ is None  # not its own cause


# ---- every list operation on a wrong-type key; bytes-like elements (i2mint/redisdol#15) --


def _wrong_type_lists():
    r = FakeRedis()
    r.set("s", "text")
    r.hset("h", "f", "v")
    return r, [RedisList(r, "s"), RedisList(r, "h")]


_READ_OPS = {
    "getitem": lambda l: l[0],
    "negative": lambda l: l[-1],
    "slice": lambda l: l[0:2],
    "stepped slice": lambda l: l[::2],
    "len": len,
    "iter": list,
    "contains": lambda l: "x" in l,
    "index": lambda l: l.index("x"),
    "count": lambda l: l.count("x"),
    "reversed": lambda l: list(reversed(l)),
    "append": lambda l: l.append("x"),
    "extend": lambda l: l.extend(["x", "y"]),
    "insert": lambda l: l.insert(0, "x"),
    "pop": lambda l: l.pop(),
    "pop0": lambda l: l.pop(0),
    "remove": lambda l: l.remove("x"),
    "clear": lambda l: l.clear(),
    "iadd": lambda l: l.__iadd__(["x"]),
    "setitem": lambda l: l.__setitem__(0, "x"),
    "delitem": lambda l: l.__delitem__(0),
}


@pytest.mark.parametrize("op", list(_READ_OPS.values()), ids=list(_READ_OPS))
def test_every_list_operation_on_a_wrong_type_key_is_a_type_error(op):
    r, lists = _wrong_type_lists()
    for lst in lists:
        with pytest.raises(TypeError, match="not a list") as info:
            op(lst)
        assert type(info.value.__cause__).__name__ == "ResponseError" or (
            info.value.__cause__ is None  # raised by our own type check (clear)
        )
    assert r.get("s") == b"text"  # nothing was destroyed
    assert r.hget("h", "f") == b"v"


def test_clear_still_deletes_lists_and_tolerates_a_missing_key():
    r = FakeRedis()
    r.rpush("l", "a", "b")
    RedisList(r, "l").clear()
    assert not r.exists("l")
    RedisList(r, "nope").clear()  # like list.clear on an empty list: no error


def test_decode_responses_connection_still_gets_type_errors():
    r = FakeRedis(decode_responses=True)
    r.set("s", "text")
    with pytest.raises(TypeError, match="not a list"):
        RedisList(r, "s").clear()
    assert r.get("s") == "text"


def test_missing_key_reads_are_unchanged():
    lst = RedisList(FakeRedis(), "nope")
    assert len(lst) == 0 and list(lst) == [] and lst[0:3] == []
    with pytest.raises(IndexError):
        lst[0]


@pytest.mark.parametrize("make", [bytearray, memoryview])
def test_bytes_like_elements_are_stored_as_their_bytes(make):
    r = FakeRedis()
    lst = RedisList(r, "l")
    lst.append(make(b"ab"))
    lst.extend([make(b"cd")])
    lst.insert(0, make(b"zz"))
    assert r.lrange("l", 0, -1) == [b"zz", b"ab", b"cd"]
    lst[0] = make(b"yy")
    assert lst[0] == b"yy"


def test_cast_memoryview_element_is_sent_by_its_bytes():
    import array

    mv = memoryview(array.array("I", [1, 2]))
    assert len(mv) == 2 and mv.nbytes == 8  # redis-py would send len(mv)
    r = FakeRedis()
    RedisList(r, "l").append(mv)
    assert r.lindex("l", 0) == bytes(mv)
    s = _store()
    s["k"] = [mv, b"x"]  # via the store's list path as well
    assert s._source.lindex("k", 0) == bytes(mv)


def test_element_codec_output_that_is_bytes_like_is_normalised():
    r = FakeRedis()
    lst = RedisList(r, "l", encode=lambda s: bytearray(s.encode()))
    lst.append("hi")
    assert r.lindex("l", 0) == b"hi"


def test_wrapped_class_of_falls_back_to_the_init_closure(monkeypatch):
    """Older dol versions don't set ``_wrapped_class`` etc.: the closure is read instead."""
    from redisdol.base import _wrapped_class_of

    W = KeyCodecs.prefixed("p:")(RedisPersister)
    assert _wrapped_class_of(W)[0] is RedisPersister
    wrap = next((c for c in W.__mro__ if "_wrapped_class" in vars(c)), None)
    for attr in ("_wrapped_class", "_wrapper_class", "_delegation_attr"):
        if wrap is not None:  # newer dol sets them; with older dol this is already the fallback
            monkeypatch.delattr(wrap, attr)
    assert _wrapped_class_of(W)[0] is RedisPersister
    s = store_from_source(FakeRedis(), W)
    s["a"] = "1"
    assert s["a"] == b"1"


def test_subclass_with_its_own_init_is_refused_and_a_mixin_in_the_mro_still_runs():
    W = KeyCodecs.prefixed("p:")(RedisPersister)

    class Y(W):  # built through its own __init__, which we can't call without a Redis(**kw)
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.extra = 1

    with pytest.raises(TypeError, match="can't be determined"):
        store_from_source(FakeRedis(), Y)

    class Mixin(Store):
        def __init__(self, store):
            super().__init__(store)
            self.mixin_ran = True

    class X(W, Mixin):
        pass

    assert store_from_source(FakeRedis(), X).mixin_ran is True
