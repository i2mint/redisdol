"""Utils for redisdol"""


def cast_to_numeric_if_possible(x):
    try:
        return int(x)
    except ValueError:
        try:
            return float(x)
        except ValueError:
            return x

