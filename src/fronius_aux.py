def flatten_json(y) -> Dict[str, Any]:
    """
    https://towardsdatascience.com/flattening-json-objects-in-python-f5343c794b10
    :param y: semi-structured JSON object
    :return: flattened JSON object
    """
    out: Dict[str, Any] = dict()

    def flatten(x, name='') -> Dict[str, Any]:
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + '_')
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, name + str(i) + '_')
                i += 1
        else:
            out[name[:-1]] = x

    flatten(y)

    return out
