"""redis with a simple (dict-like or list-like) interface

Needs python's redis package:
```
    pip install redis
```
Needs a redis server running.

To get/install Redis: https://redis.io/topics/quickstart

To launch local redis service.
```
    redis-server
```
"""

from redisdol.base import (
    RedisBytesCollection,
    RedisBytesReader,
    RedisBytesPersister,
    RedisType,
    RedisFactories,
    RedisPersister,
    RedisCollection,
    RedisList
)

