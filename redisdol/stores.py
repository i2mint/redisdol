"""Ready made convenience Redis stores"""

from dol import wrap_kvs
from redisdol.base import RedisList, RedisPersister
from redisdol.util import cast_to_numeric_if_possible


def _convert_numeric_list(data, output_type=list):
    if isinstance(data, RedisList):
        return output_type(map(cast_to_numeric_if_possible, data))
    return data  # not a list (e.g. a string value): pass through untouched


@wrap_kvs(obj_of_data=_convert_numeric_list)
class RedisStoreWithNumericLists(RedisPersister):
    """
    Redis store that converts lists of numeric strings to lists of numbers.

    >>> s = RedisStoreWithNumericLists()
    >>> s['__test_numeric_list'] = [1,-2,-3.0, 4e-23, 'not_a_number']
    >>> s['__test_numeric_list']
    [1, -2, -3.0, 4e-23, b'not_a_number']
    >>> s['__test_str'] = 'hello'
    >>> s['__test_str']  # non-list values pass through (they used to come back as None)
    b'hello'
    >>> del s['__test_numeric_list'], s['__test_str']

    Note that a list comes back as a detached python ``list`` (a snapshot): mutating
    it does not write through to Redis, unlike the `RedisList` handle of `RedisPersister`.
    """
