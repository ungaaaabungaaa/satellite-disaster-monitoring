import time
import unittest
from io import BytesIO

from satellite_monitoring.http_range import Budget, RangeFile, RangeSource

URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/test/B03.tif"


class Response(BytesIO):
    def __init__(self, content, status, headers):
        super().__init__(content)
        self.status, self.headers = status, headers


class Opener:
    def __init__(self, content=b"0123456789", status=206, etag='"pinned"'):
        self.content, self.status, self.etag = content, status, etag
        self.calls = []

    def open(self, request, timeout):
        self.calls.append(request)
        if request.get_method() == "HEAD":
            return Response(b"", 200, {"Content-Length": str(len(self.content)), "ETag": self.etag})
        start, end = map(int, request.get_header("Range").removeprefix("bytes=").split("-"))
        return Response(
            self.content[start : end + 1],
            self.status,
            {"Content-Range": f"bytes {start}-{end}/{len(self.content)}", "ETag": self.etag},
        )


class RangeTests(unittest.TestCase):
    def test_time_limit_during_a_response_is_reported_as_time_failure(self):
        opener, budget = Opener(), Budget()
        original = opener.open

        def answer(request, timeout):
            response = original(request, timeout)
            if request.get_method() != "HEAD":
                read = response.read

                def slow(size=-1):
                    value = read(size)
                    budget.started = time.monotonic() - budget.seconds - 1
                    return value

                response.read = slow
            return response

        opener.open = answer
        source = RangeSource(URL, budget, opener=opener)
        with self.assertRaisesRegex(OSError, "time"):
            RangeFile(source).read(3)

    def test_reads_exact_ranges_and_tracks_measured_bytes(self):
        opener, budget = Opener(), Budget(max_bytes=100)
        source = RangeSource(URL, budget, opener=opener)
        stream = RangeFile(source)
        self.assertEqual(stream.read(3), b"012")
        self.assertEqual(stream.seek(-2, 2), 8)
        self.assertEqual(stream.read(5), b"89")
        self.assertEqual(stream.read(1), b"")
        self.assertEqual(budget.bytes, 10)  # One cached range; count actual transferred payload.
        self.assertEqual(budget.requests, 2)
        self.assertEqual(source.ranges[0]["start"], 0)
        self.assertEqual(opener.calls[1].get_header("If-match"), '"pinned"')

    def test_small_tiff_directory_reads_share_one_bounded_cached_range(self):
        opener, budget = Opener(content=b"x" * 100000), Budget()
        stream = RangeFile(RangeSource(URL, budget, opener=opener))
        for offset in [0, 8, 42, 1510, 4096]:
            stream.seek(offset)
            self.assertEqual(stream.read(2), b"xx")
        self.assertEqual(budget.requests, 2)
        self.assertEqual(budget.bytes, 65536)

    def test_budget_and_range_support_are_required(self):
        source = RangeSource(URL, Budget(max_bytes=2), opener=Opener())
        with self.assertRaises(OSError):
            RangeFile(source).read(3)
        source = RangeSource(URL, Budget(), opener=Opener(status=200))
        with self.assertRaises(OSError):
            RangeFile(source).read(3)

    def test_refuses_changed_source_or_arbitrary_destination(self):
        with self.assertRaises(ValueError):
            RangeSource("http://127.0.0.1/file", Budget(), opener=Opener())
        with self.assertRaises(OSError):
            RangeSource(URL, Budget(), expected={"size": 10, "etag": '"other"'}, opener=Opener())


if __name__ == "__main__":
    unittest.main()
