"""Deterministic browser coverage for the extended inspector and the refreshed console."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base',default='http://127.0.0.1:8765')
parser.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parents[2]/'ui-refresh')
args=parser.parse_args()
BASE=args.base.rstrip('/')
OUT=args.output_dir
ACCOUNT='76561198000000001'
CLASS='/Game/TheIsle/Core/Characters/Dinosaurs/Example/BP_Example'
STAMP='2026-11-13T12:00:00+00:00'

def entity(id, name, species, **extra):
    values=dict(id=id,name=name,species=species,kind='player',steam_id=str(int(ACCOUNT)+id-1),class_path=CLASS,
                x=100000+(id-1)*30000,y=100000,z=100,in_scope=True,dead=False,growth=.85,last_seen=5,
                health=125,max_health=500,health_seen=5,max_health_seen=5,stamina=35,max_stamina=100,stamina_seen=5,max_stamina_seen=5,
                weight=750,weight_seen=5,blood=120,max_blood=400,blood_seen=5,max_blood_seen=5,
                food_value=50,max_food_value=200,food_seen=5,max_food_seen=5,rotten_value=7,rotten_seen=5,
                yaw=270,pitch=0,roll=0,velocity_x=300,velocity_y=400,velocity_z=0,movement_seen=5,
                group_id=77,is_group_leader=True,group_seen=5,ability_state=84,ability_seen=5,negative_effects_mask=130,effects_seen=5)
    values.update(extra);return values

EXT=['weight','weight_seen','blood','max_blood','blood_seen','max_blood_seen','food_value','max_food_value','food_seen','max_food_seen','rotten_value','rotten_seen','yaw','pitch','roll','velocity_x','velocity_y','velocity_z','movement_seen','group_id','is_group_leader','group_seen','ability_state','ability_seen','negative_effects_mask','effects_seen']
def sample(e,time,known=True):
    old=[time,e['x'],e['y'],e['z'],1,0,e['growth'],time,e['health'],e['max_health'],5,5,e['stamina'],e['max_stamina'],5,5]
    extended=[e.get(k) for k in EXT] if known else [None]*len(EXT)
    extended[20]=int(e['is_group_leader']) if known else -1
    return old+extended

owner=entity(1,'Người quan sát','Allosaurus',health=1000,max_health=2000,weight=1900,group_id=42,is_group_leader=False)
target=entity(2,'Mục tiêu thử','Carnotaurus')
ally=entity(3,'Đồng đội','Stegosaurus',group_id=42,is_group_leader=False)
fish=entity(4,'Cá không lấy','Coalecanth',kind='ai',class_path='/Game/TheIsle/Core/AI/Characters/Fish/BP_Coalecanth')
replay=dict(id='snapshot-1002',filename='synthetic.replay',recorded_at='2026-11-13T12:00:00',copied_at=STAMP,map='Gateway',duration_ms=30000,time_seconds=30,source_size=1000,history_schema=4,history_sample_seconds=1,
            entities=[owner,target,ally,fish],tracks={str(e['id']):[sample(e,0,False),sample(e,5)] for e in [owner,target,ally,fish]},diagnostics={'frames':30,'movements':30,'failed_movements':0,'warnings':0,'samples':[]},chunks={'data':1,'checkpoint':0})
replay['tracks']['2'] += [sample({**target,'negative_effects_mask':0,'effects_seen':10},10),sample({**target,'negative_effects_mask':255,'effects_seen':15},15)]
lost=sample({**target,'negative_effects_mask':128,'effects_seen':15},25);lost[4]=0
replay['tracks']['2'].append(lost)
legacy={**replay,'id':'snapshot-1001','history_schema':3,'tracks':{key:[row[:16] for row in rows] for key,rows in replay['tracks'].items()}}
state=dict(status={'phase':'idle','error':None},source_dir='D:/Synthetic',copy_dir='D:/Private',interval_seconds=20,files=[],selected_file='',replay=replay,
           history=[{k:r[k] for k in ['id','filename','copied_at','duration_ms']} for r in [replay,legacy]],player_profile={'steam_id':ACCOUNT,'name':'Người quan sát'})

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1100},reduced_motion='reduce')
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    def api(route):
        path=route.request.url.split(BASE,1)[-1].split('?',1)[0]
        values={'/api/state':state,'/api/profile':state['player_profile'],'/api/replays/snapshot-1002':replay,'/api/replays/snapshot-1001':legacy}
        route.fulfill(json=values[path]) if path in values else route.fulfill(status=404,json={'error':'Fixture route'})
    page.route('**/api/**',api)
    page.goto(BASE,wait_until='networkidle');page.wait_for_function("() => typeof viewReplay!=='undefined' && !!viewReplay")
    page.evaluate('setTime(7);selectEntity(2,false)')
    panel=page.locator('#entityDetail')
    assert 'Carnotaurus' in panel.inner_text()
    assert panel.locator('.vital-card.blood .vital-value').inner_text()=='120 / 400'
    assert panel.locator('.vital-card.blood [role=meter]').get_attribute('aria-valuenow')=='120'
    assert '750' in panel.locator('.target-measures').inner_text()
    assert '5 m/s' in panel.inner_text() and '18 km/h' in panel.inner_text()
    assert '0°' in panel.inner_text()
    assert '#77' in panel.inner_text() and 'Trưởng nhóm' in panel.inner_text()
    effects=panel.locator('.target-effects')
    assert effects.get_attribute('data-state')=='active'
    assert effects.locator('.effect-card').count()==2
    assert 'Thiếu dịch cơ thể' in effects.inner_text() and 'Gãy chân' in effects.inner_text()
    assert 'Ghi nhận ở 00:05' in effects.inner_text() and '00:02' in effects.inner_text()
    assert 'Gãy chân' in page.locator('#ownerCondition .owner-effects').inner_text()
    page.evaluate('setTime(12)')
    assert effects.get_attribute('data-state')=='clear'
    assert effects.locator('.effect-card').count()==0
    assert 'Không ghi nhận hiệu ứng bất lợi' in effects.inner_text()
    page.evaluate('setTime(17)')
    assert effects.locator('.effect-card').count()==8
    assert effects.locator('[data-effect="bGlassBones"]').inner_text().startswith('Xương giòn')
    assert effects.locator('[data-effect="bIsHeadFractured"]').inner_text().startswith('Gãy xương đầu')
    page.evaluate('setTime(27)')
    assert effects.locator('.effect-card').count()==1
    assert effects.locator('.effect-scope').is_visible()
    assert 'Trạng thái ở lần ghi cuối' in effects.inner_text()
    page.evaluate('setTime(7)')
    assert effects.locator('.effect-card').count()==2
    assert page.locator('.creature-heading-arrow[data-heading="0"]').count()>=1
    assert page.evaluate('allEntities().length')==3
    assert page.locator('#entityList').inner_text().find('Coalecanth')<0
    assert page.evaluate('currentProximity().targets.find(t=>t.entity.id===3).friendly') is True
    assert not page.locator('#radarConfigDetails').get_attribute('open')
    assert page.locator('.workspace').bounding_box()['y'] < page.locator('#radarConfigDetails').bounding_box()['y']
    page.evaluate('setTime(0)')
    assert effects.get_attribute('data-state')=='unknown'
    assert effects.locator('.effect-card').count()==0
    assert panel.locator('.vital-card.blood [role=meter]').count()==0
    assert 'Weight ghi nhận\nChưa rõ' in panel.inner_text()
    page.evaluate("loadReplay('snapshot-1001')")
    page.wait_for_function("() => viewReplay.id==='snapshot-1001'")
    page.evaluate('setTime(7);selectEntity(2,false)')
    assert panel.locator('.vital-card.blood [role=meter]').count()==0
    assert effects.get_attribute('data-state')=='unknown'
    assert effects.locator('.effect-card').count()==0
    assert 'Weight ghi nhận\nChưa rõ' in panel.inner_text()
    page.evaluate("archiveId='';loadReplay('snapshot-1002')")
    page.wait_for_function("() => viewReplay.id==='snapshot-1002'")
    page.evaluate('setTime(17);selectEntity(2,false);document.getElementById("toast").hidden=true')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'extended-desktop.png').write_bytes(page.screenshot(full_page=True))
    for width in [390,320]:
        page.set_viewport_size({'width':width,'height':844})
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'),width
        panel.scroll_into_view_if_needed()
        (OUT/f'extended-mobile-{width}.png').write_bytes(panel.screenshot())
    page.locator('#ownerConfigure').click()
    assert page.locator('#radarConfigDetails').get_attribute('open') is not None
    assert page.locator('#profileSteam').is_visible()
    assert not errors,errors
    print(json.dumps(dict(weight=True,blood=True,food=True,movement=True,groups=True,named_effects=8,effects_clear_and_unknown=True,effects_observation_time=True,owner_effects=True,coelacanth_excluded=True,legacy_timeline_isolation=True,map_first=True,mobile=[390,320],javascript_errors=errors)))
    browser.close()
