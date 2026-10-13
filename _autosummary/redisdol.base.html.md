# redisdol.base

Base objects for redisdol

### Functions

| [`store_from_source`](#redisdol.base.store_from_source)(source[, cls])      | Make a store of type `cls` (default `RedisPersister`) over a `Redis` connection.   |
|----------------------------------------------------------------------------------------|------------------------------------------------------------------------------------|
| [`store_from_sourced_object`](#redisdol.base.store_from_sourced_object)(obj[, cls]) | Like `store_from_source`, taking the connection from `obj._source`.                |

### Classes

| [`RedisBytesCollection`](#redisdol.base.RedisBytesCollection)([host, port, db, ...])       |                                                                                  |
|----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| [`RedisBytesPersister`](#redisdol.base.RedisBytesPersister)([host, port, db, ...])        | Provides a `collections.abc.MutableMapping` (i.e. dict-like) interface to Redis. |
| [`RedisBytesReader`](#redisdol.base.RedisBytesReader)([host, port, db, password, ...]) |                                                                                  |
| [`RedisCollection`](#redisdol.base.RedisCollection)([host, port, db, password, ...])  |                                                                                  |
| [`RedisFactories`](#redisdol.base.RedisFactories)()                                  | Classmethod constructors that reuse an existing `Redis` connection.              |
| [`RedisList`](#redisdol.base.RedisList)(source, name, \*[, encode, decode])     | An object to operate on Redis lists as if they were python lists                 |
| [`RedisPersister`](#redisdol.base.RedisPersister)([host, port, db, password, ...])   |                                                                                  |
| `RedisType`()                                                                                      |                                                                                  |

### *class* redisdol.base.RedisBytesCollection(host='localhost', port=6379, db=0, password=None, socket_timeout=5, socket_connect_timeout=5, socket_read_size=32768, socket_keepalive=True, socket_keepalive_options=<object object>, connection_pool=None, unix_socket_path=None, encoding='utf-8', encoding_errors='strict', decode_responses=False, retry_on_timeout=False, retry=<redis.retry.Retry object>, retry_on_error=None, ssl=False, ssl_keyfile=None, ssl_certfile=None, ssl_cert_reqs='required', ssl_include_verify_flags=None, ssl_exclude_verify_flags=None, ssl_ca_certs=None, ssl_ca_path=None, ssl_ca_data=None, ssl_check_hostname=True, ssl_password=None, ssl_validate_ocsp=False, ssl_validate_ocsp_stapled=False, ssl_ocsp_context=None, ssl_ocsp_expected_cert=None, ssl_min_version=None, ssl_ciphers=None, max_connections=None, single_connection_client=False, health_check_interval=0, client_name=None, lib_name=<object object>, lib_version=<object object>, driver_info=<object object>, username=None, redis_connect_func=None, credential_provider=None, protocol=None, legacy_responses=True, cache=None, cache_config=None, event_dispatcher=None, maint_notifications_config=None, oss_cluster_maint_notifications_handler=None)

Bases: `Collection`

### *class* redisdol.base.RedisBytesPersister(host='localhost', port=6379, db=0, password=None, socket_timeout=5, socket_connect_timeout=5, socket_read_size=32768, socket_keepalive=True, socket_keepalive_options=<object object>, connection_pool=None, unix_socket_path=None, encoding='utf-8', encoding_errors='strict', decode_responses=False, retry_on_timeout=False, retry=<redis.retry.Retry object>, retry_on_error=None, ssl=False, ssl_keyfile=None, ssl_certfile=None, ssl_cert_reqs='required', ssl_include_verify_flags=None, ssl_exclude_verify_flags=None, ssl_ca_certs=None, ssl_ca_path=None, ssl_ca_data=None, ssl_check_hostname=True, ssl_password=None, ssl_validate_ocsp=False, ssl_validate_ocsp_stapled=False, ssl_ocsp_context=None, ssl_ocsp_expected_cert=None, ssl_min_version=None, ssl_ciphers=None, max_connections=None, single_connection_client=False, health_check_interval=0, client_name=None, lib_name=<object object>, lib_version=<object object>, driver_info=<object object>, username=None, redis_connect_func=None, credential_provider=None, protocol=None, legacy_responses=True, cache=None, cache_config=None, event_dispatcher=None, maint_notifications_config=None, oss_cluster_maint_notifications_handler=None)

Bases: [`RedisBytesReader`](#redisdol.base.RedisBytesReader), `KvPersister`

Provides a `collections.abc.MutableMapping` (i.e. dict-like) interface to Redis.

Note that Redis automatically converts everything to bytes when writing, which means that
read and write are not inverse of each other in the base RedisPersister.
A serialization/deserialization layer can be added to make read and write consistent.

#### NOTE
You need to have a redis server running (on the port chosen by default by
`RedisBytesPersister`, etc.) to perform the following:

```pycon
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
```

### *class* redisdol.base.RedisBytesReader(host='localhost', port=6379, db=0, password=None, socket_timeout=5, socket_connect_timeout=5, socket_read_size=32768, socket_keepalive=True, socket_keepalive_options=<object object>, connection_pool=None, unix_socket_path=None, encoding='utf-8', encoding_errors='strict', decode_responses=False, retry_on_timeout=False, retry=<redis.retry.Retry object>, retry_on_error=None, ssl=False, ssl_keyfile=None, ssl_certfile=None, ssl_cert_reqs='required', ssl_include_verify_flags=None, ssl_exclude_verify_flags=None, ssl_ca_certs=None, ssl_ca_path=None, ssl_ca_data=None, ssl_check_hostname=True, ssl_password=None, ssl_validate_ocsp=False, ssl_validate_ocsp_stapled=False, ssl_ocsp_context=None, ssl_ocsp_expected_cert=None, ssl_min_version=None, ssl_ciphers=None, max_connections=None, single_connection_client=False, health_check_interval=0, client_name=None, lib_name=<object object>, lib_version=<object object>, driver_info=<object object>, username=None, redis_connect_func=None, credential_provider=None, protocol=None, legacy_responses=True, cache=None, cache_config=None, event_dispatcher=None, maint_notifications_config=None, oss_cluster_maint_notifications_handler=None)

Bases: [`RedisBytesCollection`](#redisdol.base.RedisBytesCollection), `KvReader`

### *class* redisdol.base.RedisCollection(host='localhost', port=6379, db=0, password=None, socket_timeout=5, socket_connect_timeout=5, socket_read_size=32768, socket_keepalive=True, socket_keepalive_options=<object object>, connection_pool=None, unix_socket_path=None, encoding='utf-8', encoding_errors='strict', decode_responses=False, retry_on_timeout=False, retry=<redis.retry.Retry object>, retry_on_error=None, ssl=False, ssl_keyfile=None, ssl_certfile=None, ssl_cert_reqs='required', ssl_include_verify_flags=None, ssl_exclude_verify_flags=None, ssl_ca_certs=None, ssl_ca_path=None, ssl_ca_data=None, ssl_check_hostname=True, ssl_password=None, ssl_validate_ocsp=False, ssl_validate_ocsp_stapled=False, ssl_ocsp_context=None, ssl_ocsp_expected_cert=None, ssl_min_version=None, ssl_ciphers=None, max_connections=None, single_connection_client=False, health_check_interval=0, client_name=None, lib_name=<object object>, lib_version=<object object>, driver_info=<object object>, username=None, redis_connect_func=None, credential_provider=None, protocol=None, legacy_responses=True, cache=None, cache_config=None, event_dispatcher=None, maint_notifications_config=None, oss_cluster_maint_notifications_handler=None)

Bases: [`RedisBytesCollection`](#redisdol.base.RedisBytesCollection)

#### list_encode *= None*

Element codecs handed to the `RedisList` this store returns (override in a
subclass, or set on an instance). `None` means raw.

### *class* redisdol.base.RedisFactories

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Classmethod constructors that reuse an existing `Redis` connection.

Kept for backward compatibility, but the store classes no longer inherit it:
a classmethod on a store’s attribute surface is re-exported *leaf-bound* by
every dol wrapper (key codec, prefix, filter…), so it hands back an
unwrapped store over the whole keyspace. Prefer the module-level
[`store_from_source()`](#redisdol.base.store_from_source) / [`store_from_sourced_object()`](#redisdol.base.store_from_sourced_object).

#### *classmethod* from_source(source)

Makes an instance initialized with attribute ‘_source’ from given source

#### *classmethod* from_sourced_object(obj)

Makes a instance initialized with ‘_source’ taken from obj._source (existence assumed)

### *class* redisdol.base.RedisList(source, name, , encode=None, decode=None)

Bases: [`MutableSequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.MutableSequence)

An object to operate on Redis lists as if they were python lists

A live handle: writes go straight to Redis. It is *raw* (no codec) unless
`encode` / `decode` are given, in which case `encode` is applied to every
element written (`__setitem__`, `append`, `extend`) and `decode` to every
element read. A codec layered on the *store* (e.g. `wrap_kvs`) cannot reach
into a handle it returns, so pass the element codec here (see
`RedisCollection.list_encode` / `list_decode`).

```pycon
>>> from fakeredis import FakeRedis
>>> l = RedisList(FakeRedis(), 'l', encode=str.upper, decode=bytes.decode)
>>> l.extend(['a', 'b']); l.append('c'); l[0] = 'z'
>>> list(l)
['Z', 'B', 'C']
```

#### append(v)

S.append(value) – append value to the end of the sequence

#### clear() → None -- remove all items from S

#### extend(iterable)

S.extend(iterable) – extend sequence by appending elements from the iterable

#### insert(i, v)

Insert `v` before position `i` (`list.insert` semantics: `i` is clamped).

LINSERT is relative to a *value* (wrong with duplicates), so the element
currently at the target position is temporarily replaced by a unique
sentinel, `v` is inserted before it, and the original is put back. This
runs in a WATCH/MULTI transaction (retried if the list changes meanwhile).

#### iter_batch_size *= 1000*

Number of elements fetched per round trip when iterating.

### *class* redisdol.base.RedisPersister(host='localhost', port=6379, db=0, password=None, socket_timeout=5, socket_connect_timeout=5, socket_read_size=32768, socket_keepalive=True, socket_keepalive_options=<object object>, connection_pool=None, unix_socket_path=None, encoding='utf-8', encoding_errors='strict', decode_responses=False, retry_on_timeout=False, retry=<redis.retry.Retry object>, retry_on_error=None, ssl=False, ssl_keyfile=None, ssl_certfile=None, ssl_cert_reqs='required', ssl_include_verify_flags=None, ssl_exclude_verify_flags=None, ssl_ca_certs=None, ssl_ca_path=None, ssl_ca_data=None, ssl_check_hostname=True, ssl_password=None, ssl_validate_ocsp=False, ssl_validate_ocsp_stapled=False, ssl_ocsp_context=None, ssl_ocsp_expected_cert=None, ssl_min_version=None, ssl_ciphers=None, max_connections=None, single_connection_client=False, health_check_interval=0, client_name=None, lib_name=<object object>, lib_version=<object object>, driver_info=<object object>, username=None, redis_connect_func=None, credential_provider=None, protocol=None, legacy_responses=True, cache=None, cache_config=None, event_dispatcher=None, maint_notifications_config=None, oss_cluster_maint_notifications_handler=None)

Bases: [`RedisCollection`](#redisdol.base.RedisCollection), [`RedisBytesPersister`](#redisdol.base.RedisBytesPersister)

### redisdol.base.store_from_source(source, cls=None)

Make a store of type `cls` (default `RedisPersister`) over a `Redis` connection.

The returned store is a plain `cls` instance: it sees the whole keyspace of
`source`. Apply any key/value codecs to the result yourself. `cls` may be a class
already wrapped with `dol` (e.g. `RedisStoreWithNumericLists`): its wrapped class is
built over `source` and wrapped as usual.

```pycon
>>> from fakeredis import FakeRedis
>>> s = store_from_source(FakeRedis())
>>> s['k'] = 'v'
>>> s['k']
b'v'
```

### redisdol.base.store_from_sourced_object(obj, cls=None)

Like `store_from_source`, taking the connection from `obj._source`.

Note this deliberately does not carry over any key/value wrapping of `obj`.
