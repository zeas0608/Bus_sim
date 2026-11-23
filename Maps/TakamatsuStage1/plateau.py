"""Read only station building tiles from the published CityGML ZIP, using HTTP byte ranges."""

import io
import json
import re
import urllib.parse
import urllib.request
import zipfile

from survey import BBOX

CATALOG = "https://www.geospatial.jp/ckan/api/3/action/package_show?id=plateau-37201-takamatsu-shi-2022"


def mesh_code(lon, lat):
    # JIS X 0410 third-order mesh (1 km). Works in Japan's eastern hemisphere.
    y, x = int(lat * 120), int((lon - 100) * 80)
    return f"{y // 80:02}{x // 80:02}{(y % 80) // 10}{(x % 80) // 10}{y % 10}{x % 10}"


class RemoteZip(io.RawIOBase):
    def __init__(self, url):
        self.url = url
        self.pos = 0
        with self.request("bytes=0-0") as reply:
            self.size = int(reply.headers["Content-Range"].split("/")[-1])

    def request(self, value):
        req = urllib.request.Request(
            self.url,
            headers={"Range": value, "Accept-Encoding": "identity", "User-Agent": "Bus_sim Stage1/1.0"},
        )
        reply = urllib.request.urlopen(req, timeout=10)
        if reply.status != 206:
            reply.close()
            raise ValueError("CityGML host does not support range requests")
        return reply

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = max(0, offset + {0: 0, 1: self.pos, 2: self.size}[whence])
        return self.pos

    def read(self, size=-1):
        stop = self.size if size < 0 else min(self.size, self.pos + size)
        if stop <= self.pos:
            return b""
        if stop - self.pos > 48 * 1024 * 1024:
            raise ValueError("CityGML range exceeds Stage 1 memory budget")
        with self.request(f"bytes={self.pos}-{stop - 1}") as reply:
            data = reply.read(stop - self.pos)
            if len(data) != stop - self.pos:
                raise IOError("Incomplete CityGML range")
        self.pos = stop
        return data


def download_tiles(cache):
    with urllib.request.urlopen(CATALOG, timeout=10) as response:
        package = json.load(response)["result"]
    license_name = (package.get("license_title") or package.get("license_id") or "").lower()
    if not any(
        s in license_name for s in ("表示", "attribution", "cc-by", "cc by", "公共データ", "政府標準")
    ):
        raise ValueError("PLATEAU dataset license needs review: " + license_name)
    candidates = []
    for r in package["resources"]:
        url = r["url"]
        if (
            urllib.parse.urlparse(url).scheme == "https"
            and "citygml" in (url + r.get("name", "")).lower()
            and ("zip" in url.lower() or r.get("format", "").lower() == "zip")
        ):
            candidates.append(r)
    if not candidates:
        raise ValueError("No CityGML ZIP in the published Takamatsu package")
    west, south, east, north = BBOX
    codes = {mesh_code(x, y) for x in (west, east) for y in (south, north)}
    for r in candidates:
        with zipfile.ZipFile(RemoteZip(r["url"])) as z:
            entries = [
                e
                for e in z.infolist()
                if "/bldg/" in "/" + e.filename.lower()
                and e.filename.split("/")[-1][:8] in codes
                and e.filename.lower().endswith(".gml")
            ]
            if not entries:
                continue
            output = []
            for entry in entries:
                if entry.file_size > 96 * 1024 * 1024:
                    raise ValueError("Building tile exceeds local import budget")
                name = entry.filename.split("/")[-1]
                if not re.fullmatch(r"[A-Za-z0-9_.-]+\.gml", name):
                    raise ValueError("Unexpected CityGML filename")
                data = z.read(entry)
                path = cache / name
                path.write_bytes(data)
                output.append(path)
            return output, dict(
                provider=r["url"],
                license=license_name,
                catalog=CATALOG,
                metadata_modified=package.get("metadata_modified"),
                members=[e.filename for e in entries],
            )
    raise ValueError("Published archives contain no building tile for this extent")
