"""Check bundled artwork, responsive layout and keyboard/map interactions on a real replay."""
import argparse
import gzip
import json
from pathlib import Path
import urllib.request

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base', default='http://127.0.0.1:8765')
parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'qa/survival')
options = parser.parse_args()
base = options.base.rstrip('/')


def read(path):
    with urllib.request.urlopen(base + path, timeout=10) as response:
        body = response.read()
        if response.headers.get('Content-Encoding') == 'gzip':
            body = gzip.decompress(body)
        return json.loads(body)


state = read('/api/state')
replay = read('/api/replays/' + state['replay']['id'])
state.pop('ui_revision', None)
owner = next(e for e in replay['entities'] if e.get('steam_id') and e.get('in_scope') and not e.get('dead'))
state['player_profile'] = {'steam_id': owner['steam_id'], 'name': 'QA observer'}

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1100}, reduced_motion='reduce')
    errors, failed_assets = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
    page.on('response', lambda response: failed_assets.append(response.url) if response.status >= 400 and '/api/' not in response.url else None)

    def api(route):
        request = route.request
        assert request.method == 'GET', 'This browser check must never change settings or send alerts'
        path = request.url.split(base, 1)[-1].split('?', 1)[0]
        values = {'/api/state': state, '/api/profile': state['player_profile'], '/api/replays/' + replay['id']: replay}
        route.fulfill(json=values[path]) if path in values else route.fulfill(status=404, json={'error': 'Unknown QA route'})

    page.route('**/api/**', api)
    page.goto(base, wait_until='networkidle')
    page.wait_for_function("() => typeof viewReplay !== 'undefined' && !!viewReplay?.tracks")
    page.evaluate('() => document.fonts.ready')
    assert page.evaluate("document.fonts.check('600 24px \"Barlow Condensed\"')")
    assert page.evaluate("[...document.fonts].some(font => font.family === 'Barlow Condensed' && font.status === 'loaded')")
    assert 'survival.css?v=' in page.locator('link[href*="survival.css"]').get_attribute('href')
    page.locator('#historyToggle').check()
    page.locator('#focusBtn').click()

    marker = page.locator('#markers .marker').first
    marker.focus()
    marker_id = marker.get_attribute('data-entity-id')
    assert marker_id is not None
    page.keyboard.press('Enter')
    assert page.evaluate('String(selected)') == marker_id
    assert page.evaluate('document.activeElement?.dataset.entityId') == marker_id, 'Selecting a marker must keep keyboard focus'
    page.evaluate('renderEntities()')
    assert page.evaluate('document.activeElement?.dataset.entityId') == marker_id, 'Refreshing the replay must keep marker focus'

    row = page.locator('#entityList .entity-row').first
    row.focus()
    row_id = row.get_attribute('data-entity-id')
    page.keyboard.press('Enter')
    assert page.evaluate('String(selected)') == row_id
    assert page.evaluate('document.activeElement?.dataset.entityId') == row_id, 'Selecting a list row must keep keyboard focus'
    page.evaluate('renderEntities()')
    assert page.evaluate('document.activeElement?.dataset.entityId') == row_id

    before = page.evaluate('view.width')
    page.locator('#zoomIn').click()
    assert page.evaluate('view.width') < before
    page.locator('#zoomOut').click()
    assert abs(page.evaluate('view.width') - before) < .001
    page.locator('#mapSvg').scroll_into_view_if_needed()
    bounds = page.locator('#mapSvg').bounding_box()
    start = page.evaluate('({x:view.x,y:view.y})')
    x, y = bounds['x'] + bounds['width'] * .15, bounds['y'] + bounds['height'] * .15
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 50, y + 35, steps=5)
    page.mouse.up()
    assert page.evaluate('view.x') != start['x'] and page.evaluate('view.y') != start['y']
    page.locator('#fitBtn').click()
    page.locator('#playersToggle').click()
    assert page.locator('#playersToggle').get_attribute('aria-pressed') == 'false'
    page.locator('#playersToggle').click()
    assert page.locator('#playersToggle').get_attribute('aria-pressed') == 'true'

    page.locator('#radarSettingsBtn').click()
    assert page.locator('#radarConfigDetails').get_attribute('open') is not None
    page.locator('#radarConfigDetails > summary').click()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    widths = [1440, 1280, 1024, 950, 768, 700, 390, 320]
    for width in widths:
        page.set_viewport_size({'width': width, 'height': 1100 if width > 700 else 844})
        page.evaluate('window.scrollTo(0,0)')
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), f'Page overflow at {width}px'
        assert page.locator('#mapContainer').bounding_box()['width'] > 200
        page.locator('#settingsBtn').click()
        assert page.locator('#settingsDialog').is_visible()
        dialog = page.locator('#settingsDialog').bounding_box()
        assert dialog['x'] >= -1 and dialog['x'] + dialog['width'] <= width + 1, f'Dialog overflow at {width}px'
        page.keyboard.press('Escape')
        assert not page.locator('#settingsDialog').is_visible()
        if width in [1440, 390, 320]:
            page.locator('#toast').evaluate('element => element.hidden=true')
            page.screenshot(path=str(options.output_dir / f'survival-{width}.png'), full_page=True)

    assert not failed_assets, failed_assets
    assert not errors, errors
    print(json.dumps(dict(real_replay=True, local_art_and_font=True, keyboard_focus_preserved=True,
                          map_zoom_and_drag=True, responsive_dialog=True, widths=widths, javascript_errors=errors)))
    browser.close()
