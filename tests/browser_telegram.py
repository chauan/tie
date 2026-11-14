"""Exercise Telegram settings with mocked API writes; never send real Telegram messages."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import urllib.request
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base', default='http://127.0.0.1:8765')
parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parents[1]/'qa')
args = parser.parse_args()
BASE = args.base


def read(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as response:
        body = response.read()
        if response.headers.get('Content-Encoding') == 'gzip':body = gzip.decompress(body)
        return json.loads(body)


state = read('/api/state')
assert state['interval_seconds'] == 20
assert 'bot_token' not in state['telegram']
snapshot = read('/api/replays/' + state['replay']['id'])
state = copy.deepcopy(state)
state.pop('ui_revision', None)  # Keep this mocked session independent of the live asset revision.
state['player_profile'] = {'steam_id':'76561198000000001', 'name':'Synthetic'}
state['telegram'].update(enabled=False, token_configured=False, chat_id='', friend_ids=[],
                         alert_larger=True, alert_low_health=True, low_health_ratio=.5, include_coordinates=False,
                         alert_own_low_blood=False,alert_target_low_blood=True,low_blood_ratio=.5)
posts = []
token = '123456789:' + 'a' * 35

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe', headless=True)
    page = browser.new_page(viewport={'width':1440, 'height':1100}, reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def api(route):
        request = route.request
        path = request.url.split(BASE, 1)[-1].split('?', 1)[0]
        if request.method == 'POST':
            body = request.post_data_json
            posts.append((path, body))
            if path == '/api/telegram':
                state['telegram'].update({k:v for k,v in body.items() if k != 'bot_token'})
                state['telegram']['token_configured'] = True
                state['telegram']['status']['message'] = 'Đợi bản replay mới.' if body['enabled'] else 'Đã tắt Telegram.'
                route.fulfill(json=state['telegram']);return
            if path == '/api/telegram/test':route.fulfill(json={'ok':True});return
            if path == '/api/config':route.fulfill(status=202, json={'queued':True});return
            raise AssertionError('Unexpected POST: ' + path)
        values = {'/api/state':state, '/api/profile':state['player_profile'], '/api/replays/' + snapshot['id']:snapshot}
        route.fulfill(json=values[path]) if path in values else route.fulfill(status=404, json={'error':'Fixture route'})
    page.route('**/api/**', api)
    page.goto(BASE, wait_until='networkidle')
    page.wait_for_function("() => typeof state!=='undefined' && !!state?.telegram && !!viewReplay")
    page.locator('#radarConfigDetails').evaluate('e=>e.open=true')
    page.locator('#telegramDetails summary').click()
    page.locator('#telegramRadius').wait_for(state='visible')
    assert page.locator('#telegramRadius').input_value() == '1000'
    assert page.locator('#telegramLarger').input_value() == '10'
    assert page.locator('#telegramLargeEnabled').is_checked()
    assert page.locator('#telegramLowHpEnabled').is_checked()
    assert page.locator('#telegramLowHpRatio').input_value() == '50'
    assert not page.locator('#telegramCoordinates').is_checked()
    assert page.locator('#telegramBloodRatio').input_value()=='50'
    assert page.locator('#telegramTargetBlood').is_checked()
    page.locator('#telegramEnabled').check()
    page.locator('#telegramToken').fill(token)
    page.locator('#telegramChat').fill('12345')
    page.locator('#telegramSave').click()
    page.wait_for_function('() => state.telegram.enabled && state.telegram.token_configured')
    assert page.locator('#telegramToken').input_value() == ''
    assert page.locator('#telegramBadge').inner_text() == 'ĐANG BẬT'
    assert posts[-1][0] == '/api/telegram'
    assert posts[-1][1]['radius_m'] == 1000 and posts[-1][1]['min_size_ratio'] == 1.1
    assert posts[-1][1]['alert_larger'] is True and posts[-1][1]['alert_low_health'] is True
    assert posts[-1][1]['low_health_ratio'] == .5 and posts[-1][1]['include_coordinates'] is False
    assert posts[-1][1]['bot_token'] == token
    page.locator('#telegramTest').click()
    page.wait_for_function("() => document.getElementById('telegramTest').disabled===false")
    assert any(path == '/api/telegram/test' for path, _ in posts)
    page.locator('#telegramLargeEnabled').uncheck()
    page.locator('#telegramCoordinates').check()
    page.locator('#telegramOwnBlood').check()
    page.locator('#telegramSave').click()
    page.wait_for_function('() => !state.telegram.alert_larger && state.telegram.include_coordinates')
    assert posts[-1][1]['alert_low_health'] is True
    assert posts[-1][1]['alert_own_low_blood'] is True and posts[-1][1]['low_blood_ratio']==.5
    page.locator('#settingsBtn').click()
    assert page.locator('#intervalInput').input_value() == '20'
    page.locator('#intervalInput').fill('30')
    page.locator('#settingsForm button[type=submit]').click()
    page.wait_for_function("() => !document.getElementById('settingsDialog').open")
    assert posts[-1][0] == '/api/config' and posts[-1][1]['interval_seconds'] == 30
    page.locator('#telegramLargeEnabled').check()
    page.locator('#telegramCoordinates').uncheck()
    page.locator('#telegramSave').click()
    page.wait_for_function('() => state.telegram.alert_larger && !state.telegram.include_coordinates')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    page.locator('#toast').evaluate('e=>e.hidden=true')
    panel = page.locator('#telegramDetails')
    panel.scroll_into_view_if_needed()
    (args.output_dir/'telegram-desktop.png').write_bytes(panel.screenshot())
    for width in [390, 320]:
        page.set_viewport_size({'width':width, 'height':844})
        panel.scroll_into_view_if_needed()
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), width
    (args.output_dir/'telegram-mobile.png').write_bytes(panel.screenshot())
    assert not errors, errors
    print(json.dumps(dict(interval_seconds=20, radius_m=1000, larger_percent=10, target_hp_below_owner_percent=50, independent_rule_toggles=True, optional_coordinates=True, settings_saved=True,
                         token_cleared_after_save=True, mock_test_message=True, mobile=[390,320], javascript_errors=errors)))
    browser.close()
