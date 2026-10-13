"""Base objects for redisdol"""

from functools import wraps
from collections.abc import Iterable
from dol.base import Collection, KvReader, KvPersister

from redis import Redis


def _identity(x):
    return x


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


def _new_with_source(cls, source):
    self = object.__new__(cls)
    self._source = source
    return self


def store_from_source(source, cls=None):
    """Make a store of type ``cls`` (default `RedisPersister`) over a ``Redis`` connection.

    The returned store is a plain, *unwrapped* ``cls`` instance: it sees the whole
    keyspace of ``source``. Apply any key/value codecs to the result yourself.

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

    def __init__(self, source, name, *, encode=None, decode=None):
        self._source = source
        self._name = name
        self._encode = encode or _identity
        self._decode = decode or _identity

    def __len__(self):
        return self._source.llen(self._name)

    def __getitem__(self, i):
        if isinstance(i, int):
            v = self._source.lindex(self._name, i)
            return v if v is None else self._decode(v)
        else:  # assume it's a slice, and modify it to conform to inclusive Redis slicing
            try:
                if i.step is not None:
                    raise NotImplementedError(
                        "Slicing is so far only implemented without step"
                    )
                return [
                    self._decode(v)
                    for v in self._source.lrange(self._name, i.start or 0, i.stop - 1)
                ]
            except AttributeError:
                raise KeyError(f"Index should be an integer or a slice object. Was {i}")

    def __iter__(self):
        # TODO: Find a more efficient way to do this.
        #   In batches perhaps? But what's the optimal batch size?
        #   async fetching of the next value/batch while yielding the one that's already fetched?
        for i in range(len(self)):
            yield self[i]

    def __setitem__(self, i, v):
        return self._source.lset(self._name, i, self._encode(v))

    def __delitem__(self, i):  # TODO: Implement
        raise NotImplementedError(
            "Don't know how to (efficiently/directly) delete a single middle item."
        )

    def append(self, v):
        # rpush (not rpushx): appending to a not-yet-existing list creates it,
        # consistently with `extend`.
        self._source.rpush(self._name, self._encode(v))

    def extend(self, iterable):
        values = [self._encode(v) for v in iterable]
        if values:  # rpush with no values is a redis error
            self._source.rpush(self._name, *values)

    def insert(self, i, v):  # TODO: Implement
        raise NotImplementedError("Might have to do with self._source.linsert")


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
        if isinstance(v, (str, bytes)):
            return super().__setitem__(k, v)
        elif isinstance(v, Iterable):
            if k in self:
                del self[k]
            encode = self._list_codec("list_encode") or _identity
            return self._source.rpush(k, *map(encode, v))
