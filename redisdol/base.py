"""Base objects for redisdol"""

import operator
import uuid
from functools import wraps
from collections.abc import Iterable
from dol.base import Collection, KvReader, KvPersister, Store

from redis import Redis
from redis.exceptions import ResponseError


def _identity(x):
    return x


def _new_sentinel():
    """A value that can't collide with real data (used to address a list position)."""
    return b"__redisdol_sentinel__" + uuid.uuid4().hex.encode()


class RedisType:
    string = b"string"
    list = b"list"


class RedisFactories:
    """Classmethod constructors that reuse an existing ``Redis`` connection.

    Kept for backward compatibility, but the store classes no longer inherit it:
    a classmethod on a store's attribute surface is re-exported *leaf-bound* by
    every dol wrapper (key codec, prefix, filter...), so it hands back an
    unwrapped store over the whole keyspace. Prefer the module-level
    :func:`store_from_source` / :func:`store_from_sourced_object`.
    """

    @classmethod
    def from_source(cls, source):
        """Makes an instance initialized with attribute '_source' from given source"""
        return _new_with_source(cls, source)

    @classmethod
    def from_sourced_object(cls, obj):
        """Makes a instance initialized with '_source' taken from obj._source (existence assumed)"""
        return cls.from_source(obj._source)


def _wrapped_class_of(cls):
    """``(wrapped class, dol's generated wrapper class)`` of a ``dol`` class-wrapper
    (``wrap_kvs``, ``KeyCodecs...``, ``filt_iter``), or ``None`` if ``cls`` is not one,
    delegates through another attribute than ``store``, or has an ``__init__`` of its
    own (a subclass of a wrapper: it must be built through that ``__init__``).

    Reads the ``_wrapped_class`` / ``_delegation_attr`` attributes dol sets on its
    generated wrapper class (dol#131), falling back, for older dol versions, to the
    closure of the ``__init__`` it generates.
    """
    init = getattr(cls, "__init__", None)
    # the generated wrapper class: the one that defines ``__init__`` and, in new dol,
    # carries the attributes in its own namespace (a subclass only inherits them)
    wrapper = next(
        (
            c
            for c in cls.__mro__
            if "_wrapped_class" in vars(c) and "__init__" in vars(c)
        ),
        None,
    )
    if wrapper is not None:
        if vars(wrapper)["__init__"] is not init:
            return None
        wrapped, attr = wrapper._wrapped_class, wrapper._delegation_attr
        if isinstance(wrapped, type) and attr == "store":
            return wrapped, wrapper
        return None
    code, cells = getattr(init, "__code__", None), getattr(init, "__closure__", None)
    if code is None or not cells:
        return None
    free = dict(zip(code.co_freevars, cells))
    if not {"wrapped", "delegation_attr", "__class__"} <= free.keys():
        return None
    try:
        wrapped = free["wrapped"].cell_contents
        attr = free["delegation_attr"].cell_contents
        wrapper = free["__class__"].cell_contents
    except ValueError:  # empty cell
        return None
    if not (
        isinstance(wrapped, type) and isinstance(wrapper, type) and attr == "store"
    ):
        return None
    return wrapped, wrapper


def _new_with_source(cls, source):
    if issubclass(cls, Store):
        # A dol-wrapped class: its instances delegate to an instance of the wrapped
        # class, so build that one over ``source`` and wrap it (i2mint/redisdol#10).
        found = _wrapped_class_of(cls)
        if found is None:
            raise TypeError(
                f"Can't build {cls.__name__} over an existing connection: it is a dol "
                "Store whose wrapped class can't be determined. Build the store over "
                "the connection first and wrap that instance instead."
            )
        wrapped, wrapper = found
        self = object.__new__(cls)
        # what dol's generated __init__ does after building the delegate: the next
        # __init__ in the instance's MRO (which may set state of its own), not Store's
        super(wrapper, self).__init__(_new_with_source(wrapped, source))
        return self
    self = object.__new__(cls)
    self._source = source
    return self


def store_from_source(source, cls=None):
    """Make a store of type ``cls`` (default `RedisPersister`) over a ``Redis`` connection.

    The returned store is a plain ``cls`` instance: it sees the whole keyspace of
    ``source``. Apply any key/value codecs to the result yourself. ``cls`` may be a class
    already wrapped with ``dol`` (e.g. `RedisStoreWithNumericLists`): its wrapped class is
    built over ``source`` and wrapped as usual.

    >>> from fakeredis import FakeRedis
    >>> s = store_from_source(FakeRedis())
    >>> s['k'] = 'v'
    >>> s['k']
    b'v'
    """
    return _new_with_source(RedisPersister if cls is None else cls, source)


def store_from_sourced_object(obj, cls=None):
    """Like `store_from_source`, taking the connection from ``obj._source``.

    Note this deliberately does not carry over any key/value wrapping of ``obj``.
    """
    return store_from_source(obj._source, cls)


# TODO: Check:
#   Redis object seems to have getitem, setitem and delitem, so might already have Mapping API


class RedisBytesCollection(Collection):
    @wraps(Redis.__init__)
    def __init__(self, **kwargs):
        self._source = Redis(**kwargs)

    def __iter__(self):
        yield from self._source.keys()

    def __getitem__(self, k):
        v = self._source.get(k)
        if v is None:
            raise KeyError(k)
        return v

    def __contains__(self, k):
        return k in self._source

    def __len__(self):
        return len(self._source.keys())  # TODO: Any source method for this?


class RedisBytesReader(RedisBytesCollection, KvReader):
    def __getitem__(self, k):
        v = self._source.get(k)
        if v is None:  # redis GET answers nil for a missing key; Mapping says KeyError
            raise KeyError(k)
        return v


class RedisBytesPersister(RedisBytesReader, KvPersister):
    """
    Provides a `collections.abc.MutableMapping` (i.e. dict-like) interface to Redis.

    Note that Redis automatically converts everything to bytes when writing, which means that
    read and write are not inverse of each other in the base RedisPersister.
    A serialization/deserialization layer can be added to make read and write consistent.

    Note: You need to have a redis server running (on the port chosen by default by
    ``RedisBytesPersister``, etc.) to perform the following:

    >>> s = RedisBytesPersister()  # plenty of params possible (all those of redis.Redis), but taking defaults.
    >>>
    >>> # clear the kehys we'll be using
    >>> keys = ['_pyst_test_str', '_pyst_test_int', '_pyst_test_float']
    >>> for k in keys:
    ...     del s[k]
    >>>
    >>> before_length = len(s)
    >>>
    >>> s['_pyst_test_str'] = 'hello'
    >>> s['_pyst_test_str']  # note you won't be getting a str but bytes
    b'hello'
    >>>
    >>> '_pyst_test_str' in s
    True
    >>>
    >>> # numbers are converted to strings then bytes
    >>> s['_pyst_test_int'] = 42
    >>> assert s['_pyst_test_int'] == b'42'
    >>> s['_pyst_test_float'] = 3.14
    >>> assert s['_pyst_test_float'] == b'3.14'
    >>>
    >>> assert len(s) == before_length + 3
    >>>
    >>> assert '_pyst_test_float' in s
    >>>
    >>> # clean up
    >>> for k in keys:
    ...     del s[k]
    >>>
    """

    write_kwargs = dict(ex=None, px=None, nx=False, xx=False, keepttl=False)

    def __setitem__(self, k, v):
        # TODO: Extend to a store that can handle some basic python types (lists, ints, floats)
        return self._source.set(k, v, **self.write_kwargs)

    def __delitem__(self, k):
        return self._source.__delitem__(k)


# TODO: Make py2store types to handle Redis value types in a consistent matter
"""Type	Commands
Sets	SADD, SCARD, SDIFF, SDIFFSTORE, SINTER, SINTERSTORE, SISMEMBER, SMEMBERS, SMOVE, 
        SPOP, SRANDMEMBER, SREM, SSCAN, SUNION, SUNIONSTORE
Hashes	HDEL, HEXISTS, HGET, HGETALL, HINCRBY, HINCRBYFLOAT, HKEYS, HLEN, HMGET, 
        HMSET, HSCAN, HSET, HSETNX, HSTRLEN, HVALS
Lists	BLPOP, BRPOP, BRPOPLPUSH, LINDEX, LINSERT, LLEN, LPOP, LPUSH, LPUSHX, LRANGE, 
        LREM, LSET, LTRIM, RPOP, RPOPLPUSH, RPUSH, RPUSHX
Strings	APPEND, BITCOUNT, BITFIELD, BITOP, BITPOS, DECR, DECRBY, GET, GETBIT, GETRANGE, GETSET, 
        INCR, INCRBY, INCRBYFLOAT, MGET, MSET, MSETNX, PSETEX, SET, SETBIT, SETEX, SETNX, 
        SETRANGE, STRLEN
"""

"""See 729 - py2store - Redis note book to see how to generate the following:
lset: (self, name, index, value)
	Set ``position`` of list ``name`` to ``value``...
lrange: (self, name, start, end)
	Return a slice of the list ``name`` between...
lpush: (self, name, *values)
	Push ``values`` onto the head of the list ``name``...
lrem: (self, name, count, value)
	Remove the first ``count`` occurrences of elements equal to ``value``...
ltrim: (self, name, start, end)
	Trim the list ``name``, removing all values not within the slice...
lpop: (self, name)
	Remove and return the first item of the list ``name``...
llen: (self, name)
	Return the length of the list ``name``...
lpushx: (self, name, value)
	Push ``value`` onto the head of the list ``name`` if ``name`` exists...
linsert: (self, name, where, refvalue, value)
	Insert ``value`` in list ``name`` either immediately before or after...
lindex: (self, name, index)
	Return the item from list ``name`` at position ``index``...

rpush: (self, name, *values)
	Push ``values`` onto the tail of the list ``name``...
rpushx: (self, name, value)
	Push ``value`` onto the tail of the list ``name`` if ``name`` exists...
rpop: (self, name)
	Remove and return the last item of the list ``name``...
rpoplpush: (self, src, dst)
	RPOP a value off of the ``src`` list and atomically LPUSH it...

blpop: (self, keys, timeout=0)
	LPOP a value off of the first non-empty list...
brpop: (self, keys, timeout=0)
	RPOP a value off of the first non-empty list...
brpoplpush: (self, src, dst, timeout=0)
	Pop a value off the tail of ``src``, push it on the head of ``dst``...
"""

from collections.abc import MutableSequence


def _translate_list_response_error(e: ResponseError, what: str):
    """The Python exception a failed list write maps to (to be raised ``from e``), or ``None``.

    ``WRONGTYPE`` (the key holds a string, hash...) is a ``TypeError``; 'no such key' and
    'index out of range' are an ``IndexError`` like a list's; anything else (READONLY,
    OOM, ...) is not an index problem: ``None``, the caller re-raises it as it is. Only
    the server's own words are read: a pipeline's message also quotes the command, and so
    the key's name.
    """
    message = str(e).rsplit("caused error: ", 1)[-1]
    if message.upper().startswith("WRONGTYPE"):
        return TypeError(f"{what}: the key holds a Redis value that is not a list")
    lowered = message.lower()
    if "no such key" in lowered or "index out of range" in lowered:
        return IndexError(f"{what} index out of range")
    return None


def _wrongtype_as_type_error(what):
    """Decorator factory: a ``WRONGTYPE`` ``ResponseError`` raised by the method becomes the
    ``TypeError`` that :func:`_translate_list_response_error` maps it to, whichever
    operation met a key that holds something other than a list. Any other error passes
    through untouched."""

    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except ResponseError as e:
                translated = _translate_list_response_error(e, what)
                if isinstance(translated, TypeError):
                    raise translated from e
                raise

        return wrapper

    return decorator


def _normalising_bytes_likes(encode):
    """``encode`` (or the identity) followed by ``bytes(...)`` for a bytes-like result.

    redis-py would send a ``memoryview`` cast to ``'I'`` by its *length* rather than its
    bytes; a bytes-like element is a redis string, as a top-level value is.
    """
    encode = encode or _identity

    def encode_element(v):
        v = encode(v)
        return bytes(v) if isinstance(v, (bytearray, memoryview)) else v

    return encode_element


def _type_name(source, name):
    """The redis type of ``name`` as bytes (``b'none'`` when it doesn't exist)."""
    t = source.type(name)
    return t.encode() if isinstance(t, str) else t


# TODO: Redis list type is more of a linked-list than a list. Better subclass deque?
class RedisList(MutableSequence):
    """
    An object to operate on Redis lists as if they were python lists

    A live handle: writes go straight to Redis. It is *raw* (no codec) unless
    ``encode`` / ``decode`` are given, in which case ``encode`` is applied to every
    element written (``__setitem__``, ``append``, ``extend``) and ``decode`` to every
    element read. A codec layered on the *store* (e.g. ``wrap_kvs``) cannot reach
    into a handle it returns, so pass the element codec here (see
    ``RedisCollection.list_encode`` / ``list_decode``).

    >>> from fakeredis import FakeRedis
    >>> l = RedisList(FakeRedis(), 'l', encode=str.upper, decode=bytes.decode)
    >>> l.extend(['a', 'b']); l.append('c'); l[0] = 'z'
    >>> list(l)
    ['Z', 'B', 'C']
    """

    #: Number of elements fetched per round trip when iterating.
    iter_batch_size = 1000

    def __init__(self, source, name, *, encode=None, decode=None):
        self._source = source
        self._name = name
        self._encode = _normalising_bytes_likes(encode)
        self._decode = decode or _identity

    @_wrongtype_as_type_error("RedisList length")
    def __len__(self):
        return self._source.llen(self._name)

    @_wrongtype_as_type_error("RedisList access")
    def __getitem__(self, i):
        if isinstance(i, slice):
            return self._get_slice(i)
        i = operator.index(i)  # TypeError for non-integers, like list
        v = self._source.lindex(self._name, i)
        if v is None:  # redis answers nil for an out of range index
            raise IndexError("RedisList index out of range")
        return self._decode(v)

    def _get_slice(self, sl):
        start, stop, step = sl.indices(len(self))
        if step == 1:
            if stop <= start:
                return []
            values = self._source.lrange(self._name, start, stop - 1)
        else:
            values = self._source.lrange(self._name, 0, -1)[sl]
        return [self._decode(v) for v in values]

    def __iter__(self):
        # One snapshot per batch (rather than one round trip per element)
        n = max(1, int(self.iter_batch_size))
        start = 0
        while True:
            try:
                batch = self._source.lrange(self._name, start, start + n - 1)
            except ResponseError as e:  # a generator: the decorator can't wrap it
                translated = _translate_list_response_error(e, "RedisList iteration")
                if isinstance(translated, TypeError):
                    raise translated from e
                raise
            for v in batch:
                yield self._decode(v)
            if len(batch) < n:
                return
            start += n

    def __setitem__(self, i, v):
        if isinstance(i, slice):
            raise NotImplementedError("Slice assignment is not supported")
        i = operator.index(i)
        try:
            self._source.lset(self._name, i, self._encode(v))
        except (
            ResponseError
        ) as e:  # redis: 'no such key' / 'index out of range' / WRONGTYPE
            translated = _translate_list_response_error(e, "RedisList assignment")
            if translated is None:
                raise
            raise translated from e

    def __delitem__(self, i):
        """Delete the element at position ``i`` (atomically).

        LREM removes by *value*, so the element is first overwritten with a unique
        sentinel, then that sentinel is removed, in one MULTI/EXEC transaction
        (correct even when the list holds duplicate values).
        """
        if isinstance(i, slice):
            raise NotImplementedError("Slice deletion is not supported")
        i = operator.index(i)
        sentinel = _new_sentinel()
        try:
            with self._source.pipeline(transaction=True) as pipe:
                pipe.lset(self._name, i, sentinel)
                pipe.lrem(self._name, 1, sentinel)
                pipe.execute()
        except ResponseError as e:
            translated = _translate_list_response_error(e, "RedisList deletion")
            if translated is None:
                raise
            raise translated from e

    @_wrongtype_as_type_error("RedisList append")
    def append(self, v):
        # rpush (not rpushx): appending to a not-yet-existing list creates it,
        # consistently with `extend`.
        self._source.rpush(self._name, self._encode(v))

    @_wrongtype_as_type_error("RedisList extend")
    def extend(self, iterable):
        values = [self._encode(v) for v in iterable]
        if values:  # rpush with no values is a redis error
            self._source.rpush(self._name, *values)

    def clear(self):
        """Delete the list. Like the other operations, refuses (``TypeError``) a key that
        holds something else, which this handle must not destroy; the check and the
        deletion are one WATCH/MULTI transaction."""
        name = self._name

        def _clear(pipe):
            if _type_name(pipe, name) not in (RedisType.list, b"none"):
                raise TypeError(
                    "RedisList clear: the key holds a Redis value that is not a list"
                )
            pipe.multi()
            pipe.delete(name)

        self._source.transaction(_clear, name)

    @_wrongtype_as_type_error("RedisList insert")
    def insert(self, i, v):
        """Insert ``v`` before position ``i`` (``list.insert`` semantics: ``i`` is clamped).

        LINSERT is relative to a *value* (wrong with duplicates), so the element
        currently at the target position is temporarily replaced by a unique
        sentinel, ``v`` is inserted before it, and the original is put back. This
        runs in a WATCH/MULTI transaction (retried if the list changes meanwhile).
        """
        i = operator.index(i)
        value = self._encode(v)
        name = self._name

        def _insert(pipe):
            n = pipe.llen(name)
            idx = i + n if i < 0 else i
            idx = min(max(idx, 0), n)
            if idx == n:
                pipe.multi()
                pipe.rpush(name, value)
                return
            original = pipe.lindex(name, idx)
            sentinel = _new_sentinel()
            pipe.multi()
            pipe.lset(name, idx, sentinel)
            pipe.linsert(name, "BEFORE", sentinel, value)
            pipe.lset(name, idx + 1, original)

        self._source.transaction(_insert, name)


# TODO: Consider if should move to stores
# The following will probably be moved to stores, since it has serialization and indexinig logic
class RedisCollection(RedisBytesCollection):
    #: Element codecs handed to the `RedisList` this store returns (override in a
    #: subclass, or set on an instance). ``None`` means raw.
    list_encode = None
    list_decode = None

    def _list_codec(self, name):
        # type(self).<name> (not self.<name>) so a plain function set as a class
        # attribute is not bound as a method; an instance attribute still wins.
        return self.__dict__.get(name, getattr(type(self), name))

    def _mk_list(self, k):
        return RedisList(
            self._source,
            k,
            encode=self._list_codec("list_encode"),
            decode=self._list_codec("list_decode"),
        )

    def __getitem__(self, k):
        val_type = self._source.type(k)
        if isinstance(val_type, str):  # connection made with decode_responses=True
            val_type = val_type.encode()
        if val_type == b"string":
            v = self._source.get(k)
            if v is None:  # expired/deleted between TYPE and GET
                raise KeyError(k)
            return v
        elif val_type == b"list":
            return self._mk_list(k)
        elif val_type == b"none":
            raise KeyError(k)
        else:  # hash, set, zset, stream...: present but not representable here
            raise TypeError(
                f"Key {k!r} holds a Redis {val_type.decode()!r}, "
                "which this store can't read (only strings and lists)"
            )


class RedisPersister(RedisCollection, RedisBytesPersister):
    def __setitem__(self, k, v):
        if isinstance(v, (bytearray, memoryview)):
            v = bytes(v)  # bytes-like: a redis string, not a list of ints
        if isinstance(v, Iterable) and not isinstance(v, (str, bytes)):
            encode = _normalising_bytes_likes(self._list_codec("list_encode"))
            values = [encode(x) for x in v]  # also consumes one-shot iterables
            if not values:
                # Redis has no empty list (a list key with no elements doesn't exist).
                # Refuse *before* touching the existing value, rather than lose it.
                raise ValueError(
                    f"Can't store an empty list at {k!r}: Redis has no empty lists. "
                    "Use `del store[k]` to remove the key."
                )
            with self._source.pipeline(transaction=True) as pipe:  # atomic replace
                pipe.delete(k)
                pipe.rpush(k, *values)
                pipe.execute()
        else:  # str, bytes, numbers...: stored as a redis string
            return super().__setitem__(k, v)
