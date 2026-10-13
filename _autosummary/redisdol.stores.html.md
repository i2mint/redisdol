# redisdol.stores

Ready made convenience Redis stores

### Classes

| [`RedisStoreWithNumericLists`](#redisdol.stores.RedisStoreWithNumericLists)([host, port, db, ...])   | Redis store that converts lists of numeric strings to lists of numbers.   |
|------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------|

### *class* redisdol.stores.RedisStoreWithNumericLists(host='localhost', port=6379, db=0, password=None, socket_timeout=5, socket_connect_timeout=5, socket_read_size=32768, socket_keepalive=True, socket_keepalive_options=<object object>, connection_pool=None, unix_socket_path=None, encoding='utf-8', encoding_errors='strict', decode_responses=False, retry_on_timeout=False, retry=<redis.retry.Retry object>, retry_on_error=None, ssl=False, ssl_keyfile=None, ssl_certfile=None, ssl_cert_reqs='required', ssl_include_verify_flags=None, ssl_exclude_verify_flags=None, ssl_ca_certs=None, ssl_ca_path=None, ssl_ca_data=None, ssl_check_hostname=True, ssl_password=None, ssl_validate_ocsp=False, ssl_validate_ocsp_stapled=False, ssl_ocsp_context=None, ssl_ocsp_expected_cert=None, ssl_min_version=None, ssl_ciphers=None, max_connections=None, single_connection_client=False, health_check_interval=0, client_name=None, lib_name=<object object>, lib_version=<object object>, driver_info=<object object>, username=None, redis_connect_func=None, credential_provider=None, protocol=None, legacy_responses=True, cache=None, cache_config=None, event_dispatcher=None, maint_notifications_config=None, oss_cluster_maint_notifications_handler=None)

Bases: `Store`

Redis store that converts lists of numeric strings to lists of numbers.

```pycon
>>> s = RedisStoreWithNumericLists()
>>> s['__test_numeric_list'] = [1,-2,-3.0, 4e-23, 'not_a_number']
>>> s['__test_numeric_list']
[1, -2, -3.0, 4e-23, b'not_a_number']
>>> del s['__test_numeric_list']
```

#### write_kwargs

dict() -> new empty dictionary
dict(mapping) -> new dictionary initialized from a mapping object’s

> (key, value) pairs

dict(iterable) -> new dictionary initialized as if via:
: d = {}
  for k, v in iterable:
  <br/>
  ```default
  d[k] = v
  ```

dict(\*\*kwargs) -> new dictionary initialized with the name=value pairs
: in the keyword argument list.  For example:  dict(one=1, two=2)
