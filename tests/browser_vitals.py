"""Read-only live checks and deterministic browser checks for replay HP and estimated mass."""
import csv
import io
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8765'
ACCOUNT='76561198000000001'
STAMP='2026-01-01T12:00:00+00:00'
PATH='/Game/TheIsle/Core/Characters/Dinosaurs/Example/BP_Example.BP_Example_C'


def fixture():
    entity=dict(id=1,kind='player',steam_id=ACCOUNT,name='ExamplePlayer',species='Example',class_path=PATH,
                x=100000,y=100000,z=100,in_scope=True,dead=True,growth=.5,last_seen=20,
                health=0,max_health=500,health_seen=20,max_health_seen=5)
    animal=dict(entity,id=2,kind='ai',steam_id=None,name='',species='Boar',dead=False,x=110000,
                class_path='/Game/TheIsle/Core/Characters/Animals/Boar/BP_Boar',health=350,max_health=350)
    replay=dict(id='snapshot-1002',filename='synthetic.replay',recorded_at='2026-01-01T12:00:00',copied_at=STAMP,
                time_seconds=30,duration_ms=30000,source_size=1000,history_schema=2,history_sample_seconds=1,map='Gateway',
                entities=[entity,animal],tracks={
                    '1':[[0,100000,100000,100,1,0,.5,0,None,None,None,None],
                         [5,100000,100000,100,1,0,.5,5,125,500,5,5],
                         [10,100000,100000,100,1,0,.5,10,50,500,10,5],
                         [20,100000,100000,100,1,1,.5,20,0,500,20,5]],
                    '2':[[0,110000,100000,100,1,0,1,0,350,350,0,0]]},
                diagnostics={'frames':30,'movements':2,'failed_movements':0,'warnings':0,'samples':[]},chunks={'data':1,'checkpoint':0})
    legacy={**replay,'id':'snapshot-1001','history_schema':1,'tracks':{key:[row[:8] for row in rows] for key,rows in replay['tracks'].items()}}
    profile={'steam_id':ACCOUNT,'name':'ExamplePlayer'}
    history=[{k:r[k] for k in ('id','filename','copied_at','duration_ms')} for r in (replay,legacy)]
    state=dict(status={'phase':'idle','error':None},source_dir='D:\\Fixtures',copy_dir='D:\\Copies',interval_seconds=60,
               files=[],selected_file='',history=history,replay=replay,player_profile=profile)
    return replay,legacy,profile,state


with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
    context=browser.new_context(viewport={'width':1440,'height':1100},reduced_motion='reduce')
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(BASE,wait_until='domcontentloaded')
    page.wait_for_function("() => typeof viewReplay!=='undefined' && !!viewReplay?.tracks",timeout=90000)
    actual=page.evaluate("""() => {
      archiveId=viewReplay.id;
      const known=allEntities().filter(e=>M.dinoVitals(e).health!==null);
      const target=known.find(e=>e.in_scope&&!e.dead&&position(e))||known[0];
      if(target)selectEntity(target.id,false);
      return {schema:viewReplay.history_schema,health_updates:viewReplay.diagnostics.health_updates,known_actors:known.length,
              interval:state.interval_seconds,detail_has_hp:document.getElementById('entityDetail').textContent.includes('HP')};
    }""")
    assert actual['schema']==2 and actual['health_updates']>0 and actual['known_actors']>0,actual
    assert actual['detail_has_hp'],actual
    assert not errors,errors
    context.close()

    context=browser.new_context(viewport={'width':1440,'height':1100},reduced_motion='reduce')
    page=context.new_page()
    page.on('pageerror',lambda error:errors.append(str(error)))
    replay,legacy,profile,state=fixture()
    def api(route):
        path=route.request.url.split(BASE,1)[-1].split('?',1)[0]
        values={'/api/state':state,'/api/profile':profile,'/api/replays/snapshot-1002':replay,'/api/replays/snapshot-1001':legacy}
        if path not in values:route.fulfill(status=404,json={'error':'Fixture route not found'});return
        route.fulfill(json=values[path])
    page.route('**/api/**',api)
    page.goto(BASE,wait_until='networkidle')
    page.wait_for_function("() => !!viewReplay?.tracks")
    page.evaluate('setTime(7);selectEntity(1,false)')
    detail=page.locator('#entityDetail')
    assert '125 / 500 HP' in detail.inner_text()
    assert '25%' in detail.inner_text()
    assert '~500 kg (ước tính từ máu tối đa)' in detail.inner_text()
    assert page.locator('.entity-health-meter').get_attribute('aria-valuenow')=='125'
    assert page.locator('.entity-health-meter').get_attribute('data-level')=='low'
    assert page.locator('.entity-health-meter>span').evaluate('e=>e.style.width')=='25%'
    assert 'HP' in page.locator('.entity-vitals').first.inner_text()
    page.evaluate('setTime(12)')
    assert '50 / 500 HP' in detail.inner_text()
    page.evaluate('setTime(0)')
    assert 'Chưa có trong replay ở mốc này' in detail.inner_text()
    assert '~500' not in detail.inner_text()
    assert page.locator('.entity-health-meter').count()==0
    page.evaluate('setTime(20)')
    assert '0 / 500 HP' in detail.inner_text()
    assert page.locator('.entity-health-meter').get_attribute('aria-valuenow')=='0'
    page.evaluate('setTime(7);selectEntity(2,false)')
    assert '350 / 350 HP' in detail.inner_text()
    assert 'Chưa có dữ liệu cân nặng' in detail.inner_text()
    assert '~350' not in detail.inner_text(),'Do not turn a boar HP maximum into kg'
    assert page.locator('.entity-health-meter').get_attribute('data-level')=='high'
    page.evaluate('selectEntity(1,false)')
    with page.expect_download() as pending:
        page.locator('#exportCsv').click()
    rows=list(csv.DictReader(io.StringIO(Path(pending.value.path()).read_text(encoding='utf-8-sig'))))
    row=next(r for r in rows if r['actor_id']=='1')
    assert row['health_hp']=='125' and row['max_health_hp']=='500' and row['health_percent']=='25'
    assert row['estimated_weight_kg_from_max_health']=='500'
    page.locator('#snapshotSelect').select_option('snapshot-1001')
    page.wait_for_function("() => viewReplay.id==='snapshot-1001'")
    page.evaluate('setTime(7);selectEntity(1,false)')
    assert 'Chưa có trong replay ở mốc này' in detail.inner_text()
    assert page.locator('.entity-health-meter').count()==0
    page.locator('#liveSnapshotBtn').click()
    page.wait_for_function("() => viewReplay.id==='snapshot-1002'")
    page.evaluate('setTime(7);selectEntity(1,false)')
    detail.scroll_into_view_if_needed()
    (ROOT/'qa').mkdir(exist_ok=True)
    detail.screenshot(path=str(ROOT/'qa/vitals-desktop.png'))
    for width in [390,320]:
        page.set_viewport_size({'width':width,'height':844})
        detail.scroll_into_view_if_needed()
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'),f'Overflow at {width}px'
    detail.screenshot(path=str(ROOT/'qa/vitals-mobile.png'))
    assert not errors,errors
    print(json.dumps({'live':actual,'hp_meter':True,'timeline':True,'legacy_missing':True,'weight_estimate_labeled':True,'animal_weight_not_inferred':True,'csv':True,'mobile':[390,320],'javascript_errors':errors}))
    context.close();browser.close()
