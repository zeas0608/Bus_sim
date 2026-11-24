"""Offline tests for the UE 5.5 Windows wheel bootstrap. No pip or network."""
import hashlib
import importlib.util
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "Maps" / "TakamatsuStage1"
SPEC = importlib.util.spec_from_file_location("stage1_bootstrap", SOURCE / "bootstrap_wheels.py")
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


class WheelBootstrapTests(unittest.TestCase):
    def test_exact_windows_pins(self):
        requirements = bootstrap.locked_hashes(SOURCE / "requirements-win64.txt")
        self.assertEqual(set(requirements), {"numpy", "shapely"})
        for name, (version, url) in bootstrap.WHEELS.items():
            pinned_version, expected_sha = requirements[name]
            self.assertEqual(version, pinned_version)
            self.assertTrue(url.startswith("https://files.pythonhosted.org/packages/"))
            self.assertEqual(
                url.rsplit("/", 1)[-1], f"{name}-{version}-cp311-cp311-win_amd64.whl"
            )
            self.assertEqual(len(expected_sha), 64)

    @staticmethod
    def make_wheel(path: Path, contents: dict[str, bytes]):
        with zipfile.ZipFile(path, "w") as archive:
            for name, body in contents.items():
                archive.writestr(name, body)

    def test_extract_normal_wheel(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            wheel = base / "x.whl"
            target = base / "target"
            self.make_wheel(wheel, {"testpkg/__init__.py": b"answer = 42\n"})
            bootstrap.unpack_safe(wheel, target)
            self.assertEqual((target / "testpkg" / "__init__.py").read_bytes(), b"answer = 42\n")

    def test_reject_zip_traversal(self):
        for bad in ("../victim.txt", "/absolute.txt", r"..\victim.txt", "C:/victim.txt"):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as d:
                base = Path(d)
                wheel = base / "x.whl"
                self.make_wheel(wheel, {bad: b"must-not-write"})
                with self.assertRaises(ValueError):
                    bootstrap.unpack_safe(wheel, base / "target")
                self.assertFalse((base / "victim.txt").exists())

    def test_download_pin_and_cache(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            payload = b"locally-generated-fixture"
            source = base / "source.bin"
            source.write_bytes(payload)
            dest = base / "cached.whl"
            expected = hashlib.sha256(payload).hexdigest()
            bootstrap.download_verified(source.as_uri(), dest, expected)
            source.unlink()  # Second invocation must reuse verified cache.
            bootstrap.download_verified("https://example.invalid/unused", dest, expected)
            self.assertEqual(dest.read_bytes(), payload)

    def test_reject_bad_sha(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            source = base / "source.bin"
            source.write_bytes(b"tampered")
            dest = base / "cached.whl"
            with self.assertRaises(ValueError):
                bootstrap.download_verified(source.as_uri(), dest, "0" * 64)
            self.assertFalse(dest.exists())
            self.assertFalse(dest.with_name(dest.name + ".part").exists())


if __name__ == "__main__":
    unittest.main()
