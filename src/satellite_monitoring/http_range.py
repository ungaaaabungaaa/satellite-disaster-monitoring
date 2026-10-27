"""Read fixed Sentinel COG assets through metered, verified HTTP byte ranges."""

import time
from dataclasses import dataclass, field
from hashlib import sha256
from io import RawIOBase
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "Asset redirects are not allowed.", headers, fp)


@dataclass
class Budget:
    max_bytes: int = 64_000_000
    max_requests: int = 256
    seconds: int = 600
    bytes: int = 0
    requests: int = 0
    started: float = field(default_factory=time.monotonic)

    def reserve(self, count=0):
        remaining = self.seconds - (time.monotonic() - self.started)
        if (
            count > self.max_bytes - self.bytes
            or self.requests >= self.max_requests
            or remaining <= 0
        ):
            raise OSError("Acquisition byte, request, or time budget exceeded.")
        self.requests += 1
        return max(0.01, min(20.0, remaining))


class RangeSource:
    def __init__(self, url, budget, expected=None, opener=None):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "sentinel-cogs.s3.us-west-2.amazonaws.com"
            or parsed.username
            or parsed.password
            or parsed.port
            or parsed.query
            or parsed.fragment
            or not parsed.path.startswith("/sentinel-s2-l2a-cogs/")
        ):
            raise ValueError("Only fixed public Sentinel COG asset URLs are supported.")
        self.url, self.budget = url, budget
        self.opener = opener or build_opener(NoRedirect())
        self.ranges = []
        self.cache = []
        self.failure = None
        with self.opener.open(Request(url, method="HEAD"), timeout=budget.reserve()) as response:
            self.size = int(response.headers.get("Content-Length", "0"))
            self.etag = response.headers.get("ETag", "")
        if not 0 < self.size <= 1_000_000_000 or not self.etag or self.etag.startswith("W/"):
            raise OSError("Asset must supply a bounded size and a strong ETag.")
        if expected and (self.size != expected["size"] or self.etag != expected["etag"]):
            raise OSError("Asset size/ETag differs from pinned provenance.")

    def read_range(self, start, count):
        count = min(count, self.size - start)
        if count <= 0:
            return b""
        if count > 8_000_000:
            raise OSError("One range read exceeds the 8 MB bound.")
        for offset, content in reversed(self.cache):
            if offset <= start and start + count <= offset + len(content):
                return content[start - offset : start - offset + count]
        # TIFF directories contain many tiny reads. Cache aligned bytes instead
        # of creating a new TLS connection for every two-byte directory field.
        first = start // 65536 * 65536
        last = min(self.size, ((start + count + 65535) // 65536) * 65536)
        if last - first > min(8_000_000, self.budget.max_bytes - self.budget.bytes):
            first, last = start, start + count
        payload = self.fetch_range(first, last - first)
        self.cache.append((first, payload))
        while sum(len(value) for _, value in self.cache) > 8_000_000 and len(self.cache) > 1:
            index = 1 if self.cache[0][0] == 0 else 0
            self.cache.pop(index)
        return payload[start - first : start - first + count]

    def fetch_range(self, start, count):
        end = start + count - 1
        request = Request(
            self.url, headers={"Range": f"bytes={start}-{end}", "If-Match": self.etag}
        )
        chunks, total = [], 0
        with self.opener.open(request, timeout=self.budget.reserve(count)) as response:
            content_range = response.headers.get("Content-Range", "")
            expected = f"bytes {start}-{end}/{self.size}"
            if (
                response.status != 206
                or content_range != expected
                or response.headers.get("ETag") != self.etag
            ):
                raise OSError("Asset did not honor the exact pinned HTTP range.")
            while content := response.read(min(65536, count - total + 1)):
                self.budget.bytes += len(content)
                total += len(content)
                if total > count or self.budget.bytes > self.budget.max_bytes:
                    raise OSError("Range response exceeded its declared byte bound.")
                if time.monotonic() - self.budget.started > self.budget.seconds:
                    raise OSError("Acquisition time budget exceeded.")
                chunks.append(content)
        if total != count:
            raise OSError("Range response was truncated.")
        payload = b"".join(chunks)
        self.ranges.append({"start": start, "count": count, "sha256": sha256(payload).hexdigest()})
        return payload


class RangeFile(RawIOBase):
    def __init__(self, source, gdal_callback=False):
        self.source, self.position = source, 0
        self.gdal_callback = gdal_callback

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        position = offset + (
            0 if whence == 0 else self.position if whence == 1 else self.source.size
        )
        if whence not in (0, 1, 2) or position < 0:
            raise ValueError("Invalid file seek.")
        self.position = position
        return position

    def read(self, size=-1):
        try:
            payload = self.source.read_range(
                self.position, self.source.size - self.position if size < 0 else size
            )
        except OSError as exc:
            if not self.gdal_callback:
                raise
            # Preserve the failure outside the C callback. GDAL receives a short
            # read and acquisition checks the recorded error before accepting data.
            self.source.failure = exc
            return b""
        self.position += len(payload)
        return payload

    def readinto(self, buffer):
        payload = self.read(len(buffer))
        buffer[: len(payload)] = payload
        return len(payload)


class AssetFilesystem:
    """The Rasterio opener sees only one known asset and no sidecar files."""

    def __init__(self, source):
        self.source = source

    def isfile(self, path):
        return str(path) == self.source.url

    def isdir(self, path):
        return False

    def ls(self, path):
        return []

    def mtime(self, path):
        return 0

    def size(self, path):
        if not self.isfile(path):
            raise FileNotFoundError(path)
        return self.source.size

    def open(self, path, mode="rb"):
        if mode not in ("r", "rb") or not self.isfile(path):
            raise FileNotFoundError(path)
        return RangeFile(self.source, gdal_callback=True)
