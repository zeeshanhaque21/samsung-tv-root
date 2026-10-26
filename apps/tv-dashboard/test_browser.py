"""Real-file Chrome checks. Requires already-installed Python Playwright and Chrome.

Run: python3 apps/tv-dashboard/test_browser.py
No HTTP server, package install, device connection, or internet required.
"""

import json
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent

MOCK = """
window.calls = [];
window.mockFailure = '';
window.tizen = {
    application: {
        launch: function (id, ok, fail) {
            calls.push(['launch', id]);
            if (mockFailure === 'throw') { throw {name: 'SecurityError'}; }
            if (mockFailure === 'timeout') { return; }
            if (mockFailure) { fail({name: mockFailure}); } else { ok(); }
        },
        getCurrentApplication: function () {return {exit: function () {calls.push(['exit']);}};}
    },
    systeminfo: {
        getPropertyValue: function (property, ok, fail) {
            calls.push(['property', property]);
            if (property !== 'VIDEOSOURCE') {throw new Error('Unexpected system property');}
            if (mockFailure === 'sources') {fail({name: 'SecurityError'}); return;}
            ok(mockFailure === 'missing' ? {connected: [], disconnected: []} : {
                connected: [{type: 'TV', number: 1}, {type: 'HDMI', number: 1}],
                disconnected: [{type: 'HDMI', number: 2}]
            });
        }
    },
    tvwindow: {
        setSource: function (source, ok, fail, type) {
            calls.push(['source', source, type]);
            if (mockFailure === 'set') {fail({name: 'NotSupportedError'}); return;}
            if (mockFailure === 'sourceThrow') {throw {name: 'SecurityError'};}
            ok(source);
        },
        show: function (ok, fail, rect, type, position) {
            calls.push(['show', rect, type, position]);
            if (mockFailure === 'show') {fail({name: 'NotSupportedError'}); return;}
            if (mockFailure === 'late') {window.lateShow = ok; return;}
            ok(rect);
        },
        hide: function (ok, fail, type) {calls.push(['hide', type]); ok();}
    }
};
"""


class DashboardBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(channel=os.environ.get('TV_HOME_BROWSER', 'chrome'), headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1920, 'height': 1080}, timezone_id='UTC')
        self.page = self.context.new_page()
        self.errors = []
        self.requests = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.on('request', lambda request: self.requests.append(request.url))
        # Block all network, including attempts not represented by DOM assets.
        self.context.route('http://**/*', lambda route: route.abort())
        self.context.route('https://**/*', lambda route: route.abort())

    def tearDown(self):
        self.assertEqual(self.errors, [])
        self.assertEqual([url for url in self.requests if not url.startswith('file:')], [])
        self.context.close()

    def load(self, mock=False, configured=False):
        if mock:
            self.context.add_init_script(MOCK)
        self.page.goto((ROOT / 'index.html').as_uri())
        self.page.locator('.tile').first.wait_for()
        if configured:
            # The event handlers close over these real configuration objects.
            self.page.evaluate("TV_HOME_APPS[0].id = 'test.youtube'")

    def active(self):
        return self.page.evaluate("Array.prototype.indexOf.call(document.querySelectorAll('.tile'), document.activeElement)")

    def press(self, key):
        self.page.keyboard.press(key)

    def status(self):
        return self.page.locator('#status').inner_text()

    def test_demo_composition_and_navigation(self):
        self.load()
        self.assertEqual(self.page.locator('.tile').count(), 8)
        self.assertEqual(self.page.locator('.setup').all_text_contents(), ['Open app', 'Open app', 'Open app', 'Setup required', 'Open app', 'Open app'])
        self.assertEqual(self.page.locator('#mode').inner_text(), 'Demo')
        self.assertEqual(self.active(), 0)
        self.press('ArrowLeft')
        self.assertEqual(self.active(), 0)
        for _ in range(5):
            self.press('ArrowRight')
        self.assertEqual(self.active(), 5)
        self.press('ArrowRight')
        self.assertEqual(self.active(), 5)
        self.press('ArrowDown')
        self.assertEqual(self.active(), 7)
        self.press('ArrowLeft')
        self.assertEqual(self.active(), 6)
        self.press('ArrowUp')
        self.assertEqual(self.active(), 0)
        self.press('Enter')
        self.assertIn('Demo: cannot open YouTube', self.status())
        self.press('ArrowDown')
        self.press('Enter')
        self.assertIn('Demo: cannot switch HDMI 1', self.status())
        self.press('ArrowUp')
        self.page.evaluate("document.getElementById('clock').textContent = '8:42 PM'; document.getElementById('date').textContent = 'Monday, October 26'")
        folder = ROOT / '.work/tv-dashboard'
        folder.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(folder / 'dashboard-1920x1080.png'))
        metrics = self.page.evaluate("""() => ({width: innerWidth, height: innerHeight,
            overflow: document.documentElement.scrollWidth > innerWidth,
            tiles: Array.from(document.querySelectorAll('.tile')).map(e => {
                var r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom];
            }), outline: getComputedStyle(document.activeElement).outlineWidth})""")
        self.assertEqual([metrics['width'], metrics['height']], [1920, 1080])
        self.assertFalse(metrics['overflow'])
        self.assertEqual(metrics['outline'], '5px')
        for left, top, right, bottom in metrics['tiles']:
            self.assertGreaterEqual(left, 60)
            self.assertGreaterEqual(top, 60)
            self.assertLessEqual(right, 1860)
            self.assertLessEqual(bottom, 940)

    def test_back_dialog_and_browser_exit(self):
        self.load()
        self.page.evaluate("document.dispatchEvent(new KeyboardEvent('keydown', {keyCode: 10009, bubbles: true}))")
        self.assertTrue(self.page.locator('#exit-dialog').is_visible())
        self.assertEqual(self.page.locator(':focus').get_attribute('id'), 'stay')
        self.press('Enter')
        self.assertEqual(self.active(), 0)
        self.press('Escape')
        self.press('ArrowRight')
        self.press('Enter')
        self.assertIn('close this browser tab', self.status())
        self.assertFalse(self.page.locator('#exit-dialog').is_visible())

    def test_app_launch_success_errors_setup_and_exit(self):
        self.load(mock=True, configured=True)
        self.page.locator('.tile').nth(3).focus()
        self.press('Enter')
        self.assertIn('setup required', self.status())
        self.assertEqual(self.page.evaluate('calls'), [])
        self.page.locator('.tile').first.focus()
        self.press('Enter')
        self.assertIn('Launch accepted', self.status())
        self.assertEqual(self.page.evaluate('calls[0]'), ['launch', 'test.youtube'])
        for failure, expected in [('NotFoundError', 'NotFoundError'), ('throw', 'SecurityError')]:
            self.page.evaluate('mockFailure = ' + json.dumps(failure))
            self.press('Enter')
            self.assertIn(expected, self.status())
        self.press('Escape')
        self.press('ArrowRight')
        self.press('Enter')
        self.assertEqual(self.page.evaluate('calls[calls.length - 1]'), ['exit'])

    def test_verified_app_ids_are_used_by_mocked_launch(self):
        self.load(mock=True)
        expected = [
            '9Ur5IzDKqV.TizenYouTube',
            'org.tizen.netflix-app',
            'evKhCgZelL.AmazonIgnitionLauncher2',
            '',
            'MCmYXNxgcu.DisneyPlus',
            'com.samsung.tv.tvPlusDeeplinker',
        ]
        self.assertEqual(self.page.evaluate('TV_HOME_APPS.map(function(app) {return app.id;})'), expected)
        for index, app_id in enumerate(expected):
            if not app_id:
                continue
            self.page.locator('.tile').nth(index).focus()
            self.press('Enter')
            self.assertEqual(self.page.evaluate('calls[calls.length - 1]'), ['launch', app_id])
        self.assertEqual(self.page.evaluate('calls.length'), 5)

    def test_hdmi_calls_back_and_transparency(self):
        self.load(mock=True)
        for index, number in [(6, 1), (7, 2)]:
            self.page.locator('.tile').nth(index).focus()
            self.press('Enter')
            calls = self.page.evaluate('calls')
            self.assertIn(['source', {'type': 'HDMI', 'number': number}, 'MAIN'], calls)
            self.assertIn(['show', ['0px', '0px', '1920px', '1080px'], 'MAIN', 'BEHIND'], calls)
            self.assertEqual(self.page.locator('body').get_attribute('class'), 'input-active')
            self.assertEqual(self.page.evaluate("getComputedStyle(document.body).backgroundColor"), 'rgba(0, 0, 0, 0)')
            self.press('Escape')
            self.assertEqual(self.page.evaluate('calls[calls.length - 1]'), ['hide', 'MAIN'])
            self.assertEqual(self.active(), index)
            self.assertFalse(self.page.locator('#input-hint').is_visible())

    def test_hdmi_uses_videosource_without_get_available_sources(self):
        self.load(mock=True)
        self.assertFalse(self.page.evaluate("'getAvailableSources' in tizen.tvwindow"))
        for index, number in [(6, 1), (7, 2)]:
            self.page.locator('.tile').nth(index).focus()
            self.press('Enter')
            calls = self.page.evaluate('calls')
            self.assertIn(['property', 'VIDEOSOURCE'], calls)
            self.assertIn(['source', {'type': 'HDMI', 'number': number}, 'MAIN'], calls)
            self.assertEqual(self.page.locator('body').get_attribute('class'), 'input-active')
            self.press('Escape')
        self.assertEqual(self.page.evaluate("calls.filter(function(call) {return call[0] === 'property';}).length"), 2)

    def test_hdmi_failures_never_show_success(self):
        self.load(mock=True)
        for failure in ['sources', 'missing', 'set', 'sourceThrow', 'show']:
            self.page.evaluate('mockFailure = ' + json.dumps(failure))
            self.page.locator('.tile').nth(6).focus()
            self.press('Enter')
            self.assertIn('Cannot open HDMI 1', self.status())
            self.assertFalse(self.page.locator('#input-hint').is_visible())
            self.assertEqual(self.active(), 6)

    def test_pending_launch_timeout_and_repeat_enter(self):
        self.load(mock=True, configured=True)
        self.page.clock.install()
        self.page.evaluate("mockFailure = 'timeout'")
        self.press('Enter')
        self.press('Enter')
        self.assertEqual(self.page.evaluate('calls.length'), 1)
        self.page.clock.fast_forward(10001)
        self.assertIn('No response', self.status())
        self.page.evaluate("mockFailure = ''")
        self.press('Enter')
        self.assertIn('Launch accepted', self.status())

    def test_hdmi_late_callback_timeout(self):
        self.load(mock=True)
        self.page.clock.install()
        self.page.evaluate("mockFailure = 'late'")
        self.page.locator('.tile').nth(6).focus()
        self.press('Enter')
        self.page.clock.fast_forward(10001)
        self.assertIn('No response', self.status())
        self.page.evaluate('lateShow()')
        self.assertFalse(self.page.locator('#input-hint').is_visible())
        self.assertEqual(self.active(), 6)

    def test_hdmi_hide_failure_retry_and_cleanup_serialization(self):
        self.load(mock=True)
        self.page.locator('.tile').nth(6).focus()
        self.press('Enter')
        self.page.evaluate("() => { tizen.tvwindow.hide = function(ok, fail) { fail({name: 'SecurityError'}); }; }")
        self.press('Escape')
        self.assertIn('HDMI close failed (SecurityError)', self.status())
        self.assertFalse(self.page.locator('#exit-dialog').is_visible())
        self.page.evaluate("() => { tizen.tvwindow.hide = function(ok) { window.finishHide = ok; }; }")
        self.press('Escape')
        self.assertIn('Returning to TV Home', self.status())
        before = self.page.evaluate('calls.length')
        self.press('Enter')
        self.assertEqual(self.page.evaluate('calls.length'), before)
        self.page.evaluate('finishHide()')
        self.assertEqual(self.active(), 6)
        self.assertIn('Back at TV Home', self.status())
        self.assertFalse(self.page.locator('#exit-dialog').is_visible())

    def test_hidden_hdmi_cleanup_and_hint_timeout(self):
        self.load(mock=True)
        self.page.clock.install()
        self.page.locator('.tile').nth(6).focus()
        self.press('Enter')
        self.assertTrue(self.page.locator('#input-hint').is_visible())
        self.page.clock.fast_forward(5001)
        self.assertFalse(self.page.locator('#input-hint').is_visible())
        self.press('ArrowRight')
        self.assertTrue(self.page.locator('#input-hint').is_visible())
        self.page.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, value: true}); document.dispatchEvent(new Event('visibilitychange'))")
        self.assertEqual(self.page.evaluate('calls[calls.length - 1]'), ['hide', 'MAIN'])
        self.assertEqual(self.page.locator('body').get_attribute('class'), '')
        self.page.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, value: false}); document.dispatchEvent(new Event('visibilitychange'))")
        self.assertEqual(self.active(), 6)

    def test_spatial_focus_uses_nearest_tile(self):
        self.load()
        self.page.locator('.tile').nth(2).focus()
        self.press('ArrowDown')
        self.assertEqual(self.active(), 7)
        self.press('ArrowUp')
        self.assertEqual(self.active(), 1)
        self.press('Tab')
        self.assertEqual(self.active(), 2)
        self.press('Shift+Tab')
        self.assertEqual(self.active(), 1)

    def test_partial_tizen_is_demo_not_success(self):
        self.context.add_init_script('window.tizen = {application: {}};')
        self.load()
        self.assertEqual(self.page.locator('#mode').inner_text(), 'Demo')
        self.press('Enter')
        self.assertIn('Demo: cannot open', self.status())
        self.press('ArrowDown')
        self.press('Enter')
        self.assertIn('Demo: cannot switch', self.status())

    def test_background_pending_app_never_closes_hdmi(self):
        self.load(mock=True, configured=True)
        self.page.clock.install()
        self.page.evaluate("mockFailure = 'timeout'")
        self.page.evaluate("() => { tizen.tvwindow.hide = function(ok, fail) { calls.push(['unexpected-hide']); fail({name: 'SecurityError'}); }; }")
        self.press('Enter')
        self.page.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, value: true}); document.dispatchEvent(new Event('visibilitychange'))")
        self.page.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, value: false}); document.dispatchEvent(new Event('visibilitychange'))")
        self.assertEqual(self.page.evaluate('calls'), [['launch', 'test.youtube']])
        self.page.clock.fast_forward(10001)
        self.assertIn('No response', self.status())
        self.press('ArrowRight')
        self.assertEqual(self.active(), 1)
        self.assertNotIn('HDMI', self.status())

    def test_app_background_before_success_callback(self):
        self.load(mock=True, configured=True)
        self.page.evaluate("() => { tizen.application.launch = function(id, ok) { calls.push(['launch', id]); window.finishLaunch = ok; }; }")
        self.press('Enter')
        self.page.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, value: true}); document.dispatchEvent(new Event('visibilitychange'))")
        self.page.evaluate('finishLaunch()')
        self.page.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, value: false}); document.dispatchEvent(new Event('visibilitychange'))")
        self.assertEqual(self.page.evaluate('calls'), [['launch', 'test.youtube']])
        self.assertIn('Launch accepted', self.status())
        self.press('ArrowRight')
        self.assertEqual(self.active(), 1)

    def test_clock_and_visibility_focus(self):
        self.load()
        self.assertRegex(self.page.locator('#clock').inner_text(), r'^\d{1,2}:\d{2} [AP]M$')
        self.assertRegex(self.page.locator('#date').inner_text(), r'^[A-Z][a-z]+, [A-Z][a-z]+ \d{1,2}$')
        self.press('ArrowRight')
        self.page.evaluate("document.activeElement.blur(); document.dispatchEvent(new Event('visibilitychange'))")
        self.assertEqual(self.active(), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
