"""Check live read-only integration, then deterministic UI cases in an isolated browser context."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8765'
ACCOUNT = '76561198000000001'
STAMP = '2026-01-01T12:00:00+00:00'


def fixture():
    owner = dict(id=1, kind='player', steam_id=ACCOUNT, name='ExamplePlayer', species='Allosaurus',
                 x=200000, y=100000, z=100, in_scope=False, dead=False, growth=.5, last_seen=40)
    entities = [owner]
    tracks = {'1': [[0, 200000, 100000, 100, 1, 0, .5, 0], [40, 200000, 100000, 100, 0, 0, .5, 40]]}
    actor_id = 2
    for col, count in enumerate([12, 10, 8, 6, 4, 2]):
        for n in range(count):
            species = 'Coalecanth' if n % 3 == 0 else 'Deer' if n % 3 == 1 else 'Boar'
            x, y = -505000 + (col + 3) * 50000 + 1000 + n * 20, -607000 + 8 * 50000 + 1000
            entities.append(dict(id=actor_id, kind='ai', steam_id=None, name='', species=species,
                                 x=x, y=y, z=100, in_scope=True, dead=False, growth=None, last_seen=5))
            tracks[str(actor_id)] = [[5, x, y, 100, 1, 0, None, 5]]
            if actor_id in (2, 3):
                tracks[str(actor_id)].append([20, x, y, 100, 0 if actor_id == 2 else 1, 1 if actor_id == 3 else 0, None, 20])
            actor_id += 1
    replay = dict(id='snapshot-1001', filename='synthetic.replay', recorded_at='2026-01-01T12:00:00',
                  copied_at=STAMP, duration_ms=60000, time_seconds=60, source_size=1000,
                  history_sample_seconds=1, entities=entities, tracks=tracks, map='Gateway',
                  chunks={'data': 1, 'checkpoint': 0}, diagnostics={'frames':60, 'movements':42, 'failed_movements':0, 'warnings':0, 'samples':[]})
    profile = dict(steam_id=ACCOUNT, name='ExamplePlayer')
    state = dict(status={'phase':'idle', 'error':None}, source_dir='D:\\Fixtures', copy_dir='D:\\Copies',
                 interval_seconds=60, selected_file='', files=[], history=[], replay=replay, player_profile=profile)
    return replay, profile, state


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe', headless=True)
    context = browser.new_context(viewport={'width':1440,'height':1100}, reduced_motion='reduce')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE, wait_until='domcontentloaded')
    page.wait_for_function("() => typeof viewReplay!=='undefined' && !!viewReplay?.tracks", timeout=90000)
    actual = page.evaluate("""() => {
      archiveId=viewReplay.id;
      const expected=new Set(allEntities().filter(e=>e.kind==='ai'&&e.in_scope&&!e.dead&&position(e)).map(e=>e.id)).size;
      const report=currentAiDensity();
      return {expected,total:report.total,cells:report.cells.length,rects:document.querySelectorAll('#aiDensityOverlay rect').length,interval:state.interval_seconds};
    }""")
    assert actual['expected'] == actual['total'], actual
    assert actual['cells'] == actual['rects'], actual
    assert not errors, errors
    context.close()

    context = browser.new_context(viewport={'width':1440,'height':1100}, reduced_motion='reduce')
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    replay, profile, state = fixture()

    def api(route):
        path = route.request.url.split(BASE, 1)[-1].split('?', 1)[0]
        if path == '/api/state':
            response = state
        elif path == '/api/profile':
            response = profile
        elif path == '/api/replays/snapshot-1001':
            response = replay
        else:
            route.fulfill(status=404, json={'error':'Fixture route not found'})
            return
        route.fulfill(json=response)

    page.route('**/api/**', api)
    page.goto(BASE, wait_until='networkidle')
    page.wait_for_function("() => typeof viewReplay!=='undefined' && !!viewReplay?.tracks")
    assert page.evaluate('currentAiDensity().total') == 40
    assert page.locator('.ai-density-card').count() == 5
    assert page.locator('#aiDensityOverlay rect').count() == 6
    assert 'Chưa có vị trí' in page.locator('.ai-density-direction').first.inner_text()
    page.locator('#aiDensityMore').click()
    assert page.locator('.ai-density-card').count() == 6
    assert page.locator('#aiDensityMore').get_attribute('aria-expanded') == 'true'
    page.evaluate('setTime(10)')
    assert page.evaluate('currentAiDensity().total') == 42
    assert '~' in page.locator('.ai-density-direction').first.inner_text()
    page.locator('#aiDensityToggle').uncheck()
    assert page.locator('#aiDensityOverlay rect').count() == 0
    page.evaluate("saveFollow({steam_id:playerProfile.steam_id,entity_id:1})")
    page.locator('.ai-density-card').first.click()
    assert page.locator('#aiDensityToggle').is_checked()
    assert page.evaluate('followKey===null')
    assert page.evaluate('view.width < 2000 && aiDensitySelected===currentAiDensity().cells[0].id')
    assert page.locator('.ai-density-card.selected').count() == 1
    for size in ['250', '1000', '500']:
        page.locator('#aiDensitySize').select_option(size)
        assert page.evaluate('currentAiDensity().total') == 42
        assert page.locator('#aiDensityOverlay rect').count() == page.evaluate('currentAiDensity().cells.length')
    page.locator('#aiDensitySpecies').select_option('Deer')
    expected_deer = sum(e['kind'] == 'ai' and e['species'] == 'Deer' for e in replay['entities'])
    assert page.evaluate('currentAiDensity().total') == expected_deer
    assert page.evaluate("currentAiDensity().cells.every(c=>c.species.every(s=>s.name==='Deer'))")
    page.locator('#historyToggle').check()
    page.evaluate('setTime(30)')
    assert page.evaluate('currentAiDensity().total') == expected_deer - 1, 'History ghosts must not enter density counts'
    page.locator('#aiToggle').click()
    assert page.evaluate('currentAiDensity().total') == expected_deer - 1, 'Marker visibility does not change density statistics'
    page.locator('#aiToggle').click()
    page.locator('#aiDensityFit').click()
    assert page.evaluate('aiDensitySelected===null')
    page.evaluate('setTime(0)')
    assert page.evaluate('currentAiDensity().total') == 0
    assert page.locator('#aiDensityOverlay rect').count() == 0
    assert page.locator('#aiDensityFit').is_disabled()
    assert page.locator('.ai-density-empty').is_visible()
    page.evaluate('setTime(10)')
    page.reload(wait_until='networkidle')
    page.wait_for_function("() => !!viewReplay?.tracks")
    assert page.locator('#aiDensitySpecies').input_value() == 'Deer', 'Remember settings after reload'
    assert page.locator('#aiDensitySize').input_value() == '500'
    page.evaluate('setTime(10)')
    page.locator('#aiDensitySpecies').select_option('')
    page.locator('#aiDensityPanel').scroll_into_view_if_needed()
    (ROOT/'qa').mkdir(exist_ok=True)
    page.locator('#aiDensityPanel').screenshot(path=str(ROOT/'qa/ai-density-desktop.png'))
    page.locator('.ai-density-card').first.click()
    page.locator('#mapContainer').screenshot(path=str(ROOT/'qa/ai-density-map.png'))
    for width in [390, 320]:
        page.set_viewport_size({'width':width,'height':844})
        page.locator('#aiDensityPanel').scroll_into_view_if_needed()
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'), f'Overflow at {width}px'
    page.locator('#aiDensityPanel').screenshot(path=str(ROOT/'qa/ai-density-mobile.png'))
    assert not errors, errors
    print(json.dumps({'live':actual,'fixture_ai':42,'grid_sizes':[250,500,1000], 'species':True,'timeline':True,'map_focus':True,'persisted_settings':True,'mobile':[390,320],'javascript_errors':errors}))
    context.close()
    browser.close()
