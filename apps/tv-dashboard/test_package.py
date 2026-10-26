"""Dependency-free source/package checks: python3 apps/tv-dashboard/test_package.py."""

from pathlib import Path
import tempfile
import unittest
import zipfile

from package import FILES, ROOT, build, validate, validate_archive


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.contents = {name: (ROOT / name).read_bytes() for name in FILES}

    def test_real_unsigned_package(self):
        work = ROOT / '.work'
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work) as directory:
            path = build(Path(directory) / 'test-unsigned.wgt')
            validate_archive(path)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(set(archive.namelist()), set(FILES))
                self.assertNotIn('author-signature.xml', archive.namelist())
            with self.assertRaises(FileExistsError):
                build(path)

    def test_rejects_external_html(self):
        self.contents['index.html'] += b'<script src="https://example.invalid/tracker.js"></script>'
        with self.assertRaisesRegex(ValueError, 'Non-local'):
            validate(self.contents)

    def test_rejects_wrong_platform(self):
        self.contents['config.xml'] = self.contents['config.xml'].replace(b'required_version="4.0"', b'required_version="6.0"')
        with self.assertRaisesRegex(ValueError, 'Tizen 4.0'):
            validate(self.contents)

    def test_rejects_private_material_and_build_outputs(self):
        for name in ['author.p12', 'signature1.xml', 'build/debug.log', '../config.xml']:
            with self.subTest(name=name):
                contents = dict(self.contents)
                contents[name] = b'not allowed'
                with self.assertRaisesRegex(ValueError, 'allowlisted'):
                    validate(contents)

    def test_rejects_additional_privileges(self):
        self.contents['config.xml'] = self.contents['config.xml'].replace(b'</widget>', b'<tizen:privilege name="http://tizen.org/privilege/internet"/></widget>')
        with self.assertRaisesRegex(ValueError, 'privileges'):
            validate(self.contents)

    def test_rejects_css_network_and_missing_icon(self):
        contents = dict(self.contents)
        contents['style.css'] += b'@import "https://example.invalid/style.css";'
        with self.assertRaisesRegex(ValueError, 'fetch assets'):
            validate(contents)
        del self.contents['icon.png']
        with self.assertRaises(ValueError):
            validate(self.contents)


if __name__ == '__main__':
    unittest.main(verbosity=2)
