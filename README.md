
# redisdol
redis with a simple (dict-like or list-like) interface


To install:	```pip install redisdol```


Provides a `collections.abc.MutableMapping` (i.e. dict-like) interface to Redis.

Note that Redis automatically converts everything to bytes when writing, which means that
read and write are not inverse of each other in the base RedisPersister.
A serialization/deserialization layer can be added to make read and write consistent.

```python
>>> from redisdol import RedisBytesPersister
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
>>>
>>> # numbers are converted to strings then bytes
>>> s['_pyst_test_int'] = 42
>>> assert s['_pyst_test_int'] == b'42'
>>> s['_pyst_test_float'] = 3.14
>>> assert s['_pyst_test_float'] == b'3.14'
>>>
>>> assert len(s) == before_length + 3
>>>
>>> '_pyst_test_float' in
>>>
>>> # clean up
>>> for k in keys:
...     del s[k]
>>>
```
