import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
streams = Package().load('java_stdlib.io')


class MemoryStreamTests(unittest.TestCase):
    def test_shared_buffer_marks_and_eof(self):
        buffer = bytearray([1, 128, 255, 4])
        stream = streams.ByteArrayInputStream(buffer, 1, 99)
        buffer[1] = 129
        self.assertEqual(stream.read(), 129)
        stream.mark(0)
        target = [0, 0, 0]
        self.assertEqual(stream.read(target, 1, 2), 2)
        self.assertEqual(target, [0, -1, 4])
        self.assertEqual(stream.read(), -1)
        self.assertEqual(stream.read([], 0, 0), -1)
        stream.reset()
        stream.close()
        self.assertEqual(stream.available(), 2)
        self.assertEqual(stream.skip(-10), 0)
        self.assertEqual(stream.skip(10), 2)
        with self.assertRaises(IndexError):
            stream.read(target, -1, 2)

    def test_output_copy_reset_and_charset(self):
        stream = streams.ByteArrayOutputStream()
        stream.write(255)
        stream.write([65, 66, 67], 1, 2)
        copy = stream.toByteArray()
        copy[0] = 0
        self.assertEqual(list(stream.toByteArray()), [-1, 66, 67])
        other = streams.ByteArrayOutputStream()
        stream.writeTo(other)
        self.assertEqual(list(other.toByteArray()), list(stream.toByteArray()))
        stream.reset()
        stream.close()
        stream.write(bytearray(b'hello'))
        self.assertEqual(stream.toString('utf-8'), 'hello')
        with self.assertRaises(NotImplementedError):
            stream.toString()


if __name__ == '__main__':
    unittest.main()
