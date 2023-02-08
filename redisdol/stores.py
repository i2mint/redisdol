"""Ready made convenience Redis stores"""


from dol import wrap_kvs
from redisdol.base import RedisList, RedisPersister
from redisdol.util import cast_to_numeric_if_possible


def _convert_numeric_list(data, output_type=list):
    if isinstance(data, RedisList):
        return output_type(map(cast_to_numeric_if_possible, data))


@wrap_kvs(obj_of_data=_convert_numeric_list)
class RedisStoreWithNumericLists(RedisPersister):
    """
    Redis store that converts lists of numeric strings to lists of numbers.
    
    >>> s = RedisStoreWithNumericLists()
    >>> s['__test_numeric_list'] = [1,-2,-3.0, 4e-23, 'not_a_number']
    >>> s['__test_numeric_list']
    [1, -2, -3.0, 4e-23, b'not_a_number']
    >>> del s['__test_numeric_list']
    """


