"""Java 21 integer token values, independent of Python's unlimited integer width."""
import re

INTEGER_KINDS = {'decimal_integer_literal', 'hex_integer_literal',
                 'octal_integer_literal', 'binary_integer_literal'}
PATTERNS = {
    'decimal_integer_literal': (r'(?:0|[1-9](?:[0-9_]*[0-9])?)', 10),
    'hex_integer_literal': (r'0[xX][0-9a-fA-F](?:[0-9a-fA-F_]*[0-9a-fA-F])?', 16),
    'octal_integer_literal': (r'0[0-7_]*[0-7]', 8),
    'binary_integer_literal': (r'0[bB][01](?:[01_]*[01])?', 2),
}


def literal_value(node, token, error_type, allow_decimal_min=False):
    pattern, radix = PATTERNS[node['kind']]
    is_long = token[-1:] in ('L', 'l')
    digits = token[:-1] if is_long else token
    if re.fullmatch(pattern, digits) is None:
        raise error_type(node, 'Invalid/unsupported Java integer token: ' + token)
    width = 64 if is_long else 32
    number = int(digits.replace('_', ''), radix)
    if radix == 10:
        maximum = (1 << (width - 1)) - 1 + int(allow_decimal_min)
        if number > maximum:
            raise error_type(node, 'Decimal integer literal exceeds Java signed width: ' + token)
    else:
        if number >= (1 << width):
            raise error_type(node, 'Integer bit pattern exceeds Java width: ' + token)
        if number >= (1 << (width - 1)):
            number -= (1 << width)
    return number, width
