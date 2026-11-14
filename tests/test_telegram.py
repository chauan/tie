"""Telegram behavior with synthetic replay data and a mocked transport; no real messages."""
import copy
import datetime as dt
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import telegram_alerts as alerts
import replay_service as app

TOKEN = '123456789:' + 'a' * 35
OWNER = '76561198000000001'
OTHER = '76561198000000002'
NOW = dt.datetime(2026, 11, 13, 8, 0, tzinfo=dt.timezone.utc)
CLASS = '/Game/TheIsle/Core/Characters/Dinosaurs/Example/BP_Example'


def entity(id, steam, weight, x, **extra):
    return dict(id=id, steam_id=steam, kind='player', species='Synthetic', class_path=CLASS,
                max_health=weight, health=100, x=x, y=100000, z=100, in_scope=True,
                dead=False, last_seen=id, **extra)


def replay(entities=None, time=1, now=NOW):
    return dict(entities=entities if entities is not None else [entity(1, OWNER, 1000, 100000), entity(2, OTHER, 1100, 200000)],
                time_seconds=time, filename='synthetic.replay', recorded_at='2026-11-13T08:00:00',
                source_modified_at=now.isoformat(), copied_at=now.isoformat())


class TelegramTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.alerts = alerts.TelegramAlerts(self.tmp.name)
        self.alerts.configure(dict(enabled=True, bot_token=TOKEN, chat_id='12345', alert_own_low_blood=False, alert_target_low_blood=False))
        self.sender = patch('telegram_alerts.send_message', return_value=(True, '', 0))
        self.send = self.sender.start()

    def tearDown(self):
        self.alerts.close()
        self.sender.stop()
        self.tmp.cleanup()

    def evaluate(self, data, now=NOW):
        self.alerts.process(data, {'steam_id': OWNER}, now)

    def test_exact_thresholds_no_repetition_and_closer_levels(self):
        data = replay()
        self.evaluate(data)
        self.send.assert_called_once()
        self.assertEqual(self.send.call_args.args[:2], (TOKEN, '12345'))
        self.assertIn('LỚN HƠN', self.send.call_args.args[2])
        data['time_seconds'] = 21
        self.evaluate(data, NOW + dt.timedelta(seconds=20))
        self.assertEqual(self.send.call_count, 1)
        data['entities'][1]['x'] = 150000
        data['time_seconds'] = 41
        self.evaluate(data, NOW + dt.timedelta(seconds=40))
        self.assertEqual(self.send.call_count, 2)
        data['entities'][1]['x'] = 125000
        data['time_seconds'] = 61
        self.evaluate(data, NOW + dt.timedelta(seconds=60))
        self.assertEqual(self.send.call_count, 3)
        data['entities'][1]['x'] = 150001
        data['time_seconds'] = 81
        self.evaluate(data, NOW + dt.timedelta(seconds=80))
        self.assertEqual(self.send.call_count, 3, 'Crossing a previous boundary cannot repeat an alert')

    def test_rejects_small_far_dead_lost_unknown_mass_and_friends(self):
        variants = [dict(max_health=1099), dict(x=200001), dict(dead=True), dict(health=0),
                    dict(in_scope=False), dict(max_health=None), dict(x=float('nan')),
                    dict(class_path='/Game/TheIsle/Core/Characters/Animals/Boar')]
        for changes in variants:
            data = replay(); data['entities'][1].update(changes)
            self.evaluate(data)
        self.assertEqual(self.send.call_count, 0)
        self.alerts.configure({'friend_ids': [OTHER]})
        self.evaluate(replay())
        self.assertEqual(self.send.call_count, 0)

    def test_owner_missing_dead_or_without_size_pauses(self):
        for changes in [dict(dead=True), dict(health=0), dict(max_health=None), dict(in_scope=False), dict(steam_id='different')]:
            data = replay();data['entities'][0].update(changes)
            self.evaluate(data)
        self.send.assert_not_called()

    def test_stale_source_and_repeated_replay_time_do_not_send(self):
        self.evaluate(replay(now=NOW - dt.timedelta(seconds=91)))
        self.send.assert_not_called()
        self.evaluate(replay())
        data = replay();data['entities'][1]['x'] = 110000
        self.evaluate(data)
        self.assertEqual(self.send.call_count, 1, 'A copied replay with no new frame cannot generate another alert')

    def test_latest_actor_wins_before_distance_or_death_filtering(self):
        data = replay()
        new = {**data['entities'][1], 'id': 20, 'last_seen': 20, 'x': 300000}
        data['entities'].append(new)
        self.evaluate(data)
        self.send.assert_not_called()
        data['entities'][2].update(x=150000, dead=True)
        data['time_seconds'] = 2
        self.evaluate(data)
        self.send.assert_not_called()

    def test_restart_preserves_successful_encounter_and_reentry_cooldown(self):
        self.evaluate(replay())
        restarted = alerts.TelegramAlerts(self.tmp.name)
        restarted.process(replay(time=21), {'steam_id': OWNER}, NOW + dt.timedelta(seconds=20))
        self.assertEqual(self.send.call_count, 1)
        self.evaluate(replay(entities=[entity(1, OWNER, 1000, 100000)], time=41), NOW + dt.timedelta(seconds=40))
        self.evaluate(replay(time=61), NOW + dt.timedelta(seconds=60))
        self.assertEqual(self.send.call_count, 1)
        self.evaluate(replay(entities=[entity(1, OWNER, 1000, 100000)], time=101, now=NOW + dt.timedelta(seconds=100)), NOW + dt.timedelta(seconds=100))
        self.evaluate(replay(time=141, now=NOW + dt.timedelta(seconds=140)), NOW + dt.timedelta(seconds=140))
        self.assertEqual(self.send.call_count, 2)

    def test_failed_delivery_is_retried_and_does_not_mark_as_sent(self):
        self.send.return_value = (False, 'Temporary problem', 60)
        self.evaluate(replay())
        self.evaluate(replay(time=21), NOW + dt.timedelta(seconds=20))
        self.assertEqual(self.send.call_count, 1)
        self.send.return_value = (True, '', 0)
        self.evaluate(replay(time=61), NOW + dt.timedelta(seconds=60))
        self.assertEqual(self.send.call_count, 2)
        self.assertIsNone(self.alerts.public()['status']['error'])

    def test_configuration_hides_token_preserves_blank_and_disables_sending(self):
        public = self.alerts.configure({'bot_token': ''})
        self.assertNotIn(TOKEN, json.dumps(public))
        self.assertTrue(public['token_configured'])
        self.assertEqual(self.alerts.config['bot_token'], TOKEN)
        self.alerts.configure({'enabled': False})
        self.evaluate(replay())
        self.send.assert_not_called()
        for body in [{'radius_m': float('nan')}, {'min_size_ratio': 0}, {'enabled': 1}, {'chat_id': 'invalid'}, {'friend_ids': ['bad']}, {'bot_token': TOKEN + '/bad'}, {'low_health_ratio':0}, {'low_health_ratio':1.1}, {'alert_low_health':1}, {'include_coordinates':'yes'}]:
            with self.assertRaises(ValueError):self.alerts.configure(body)

    def test_background_sender_does_not_block_status_or_snapshot_submission(self):
        entered, release = threading.Event(), threading.Event()
        def slow(*args):
            entered.set();release.wait(3);return True, '', 0
        self.send.side_effect = slow
        self.alerts.start()
        data = replay(now=dt.datetime.now(dt.timezone.utc))
        self.alerts.submit(data, {'steam_id': OWNER})
        self.assertTrue(entered.wait(2))
        try:
            self.assertTrue(self.alerts.public()['enabled'])
            self.alerts.submit({**data, 'time_seconds': 2}, {'steam_id': OWNER})
        finally:release.set()

    def test_low_health_is_independent_of_weight_and_compares_current_hp(self):
        data = replay()
        data['entities'][0].update(health=1000, max_health=2000)
        data['entities'][1].update(health=500, max_health=900)
        self.evaluate(data)
        self.send.assert_not_called()  # Exactly half is not below half.
        data['entities'][1]['health'] = 499
        data['time_seconds'] = 21
        self.evaluate(data, NOW + dt.timedelta(seconds=20))
        text = self.send.call_args.args[2]
        self.assertIn('HP MỤC TIÊU <50% HP CỦA BẠN', text)
        self.assertIn('49.9% HP của bạn', text)
        self.assertNotIn('LỚN HƠN', text)

    def test_new_low_hp_condition_alerts_after_size_alert_without_waiting_for_distance_change(self):
        data = replay();self.evaluate(data)
        data['entities'][1]['health'] = 49;data['time_seconds'] = 21
        self.evaluate(data, NOW + dt.timedelta(seconds=20))
        self.assertEqual(self.send.call_count, 2)
        text = self.send.call_args.args[2]
        self.assertIn('HP MỤC TIÊU', text);self.assertNotIn('LỚN HƠN', text)
        data['entities'][1]['x'] = 150000;data['time_seconds'] = 41
        self.evaluate(data, NOW + dt.timedelta(seconds=40))
        self.assertEqual(self.send.call_count, 3)
        text = self.send.call_args.args[2]
        self.assertIn('HP MỤC TIÊU', text);self.assertIn('LỚN HƠN', text)
        data['time_seconds'] = 61
        self.evaluate(data, NOW + dt.timedelta(seconds=60))
        self.assertEqual(self.send.call_count, 3)

    def test_low_hp_works_without_maximum_hp_and_skips_unknown_current_hp(self):
        self.alerts.configure({'alert_larger':False})
        for index, value in enumerate([None, -1, float('nan'), '49', 0]):
            data = replay(time=index+1);data['entities'][1].update(health=value, max_health=None)
            self.evaluate(data)
        self.send.assert_not_called()
        data = replay(time=21);data['entities'][0]['max_health'] = None
        data['entities'][1].update(health=49, max_health=None, stamina=None)
        self.evaluate(data)
        self.send.assert_called_once()
        text = self.send.call_args.args[2]
        self.assertIn('Kích thước ước tính: chưa rõ', text)
        self.assertIn('Stamina: chưa rõ', text)
        self.assertIn('49.0% HP của bạn', text)

    def test_low_hp_can_be_disabled_and_both_conditions_cannot_be_disabled_while_enabled(self):
        self.alerts.configure({'alert_low_health':False})
        data = replay();data['entities'][1].update(max_health=900, health=1)
        self.evaluate(data);self.send.assert_not_called()
        with self.assertRaises(ValueError):self.alerts.configure({'alert_larger':False})

    def test_known_game_group_is_ignored_but_unknown_group_is_not(self):
        data=replay();data['entities'][0]['group_id']=-123;data['entities'][1]['group_id']=-123
        self.evaluate(data);self.send.assert_not_called()
        data['entities'][1]['group_id']=0;data['time_seconds']=21
        self.evaluate(data);self.send.assert_called_once()

    def test_own_low_blood_alert_is_independent_and_deduplicated(self):
        self.alerts.configure({'alert_larger':False,'alert_low_health':False,'alert_own_low_blood':True,'low_blood_ratio':.25})
        data=replay();data['entities'][0].update(blood=250,max_blood=1000)
        self.evaluate(data);self.send.assert_not_called()
        data['entities'][0]['blood']=249;data['time_seconds']=21
        self.evaluate(data);self.send.assert_called_once()
        text=self.send.call_args.args[2]
        self.assertIn('BLOOD CỦA BẠN',text);self.assertNotIn('mức gần',text)
        data['time_seconds']=41;self.evaluate(data);self.assertEqual(self.send.call_count,1)
        data['entities'][0]['blood']=100;data['time_seconds']=61
        self.evaluate(data);self.assertEqual(self.send.call_count,2,'Further blood loss escalates without repeated same-level messages')

    def test_target_low_blood_requires_observed_current_blood_for_both_dinosaurs(self):
        self.alerts.configure({'alert_larger':False,'alert_low_health':False,'alert_target_low_blood':True})
        data=replay();data['entities'][1].update(blood=10,max_blood=None)
        self.evaluate(data);self.send.assert_not_called()
        data['entities'][0]['blood']=100;data['time_seconds']=21
        self.evaluate(data);self.send.assert_called_once()
        self.assertIn('BLOOD MỤC TIÊU <50% BLOOD CỦA BẠN',self.send.call_args.args[2])
        self.assertIn('10.0% Blood của bạn',self.send.call_args.args[2])

    def test_target_blood_strict_half_threshold_and_1000_meter_limit(self):
        self.alerts.configure({'alert_larger':False,'alert_low_health':False,'alert_target_low_blood':True,'low_blood_ratio':.5})
        data=replay();data['entities'][0].update(blood=1000,max_blood=2000);data['entities'][1].update(blood=500,max_blood=1000)
        self.evaluate(data);self.send.assert_not_called()
        data['entities'][1].update(blood=499,x=200001);data['time_seconds']=21
        self.evaluate(data);self.send.assert_not_called()
        data['entities'][1]['x']=200000;data['time_seconds']=41
        self.evaluate(data);self.send.assert_called_once()
        self.assertIn('BLOOD MỤC TIÊU <50%',self.send.call_args.args[2])

    def test_target_blood_does_not_use_the_targets_or_owners_maximum(self):
        self.alerts.configure({'alert_larger':False,'alert_low_health':False,'alert_target_low_blood':True})
        data=replay();data['entities'][0].update(blood=100,max_blood=1000)
        data['entities'][1].update(blood=200,max_blood=1000)
        self.evaluate(data);self.send.assert_not_called()  # Target is 20% full, but has twice your current Blood.
        data['entities'][0]['blood']=1000;data['entities'][1].update(blood=499,max_blood=500);data['time_seconds']=21
        self.evaluate(data);self.send.assert_called_once()  # Target is almost full, but has less than half your Blood.

    def test_changing_blood_basis_rearms_only_the_blood_condition(self):
        self.alerts.configure({'alert_target_low_blood':True})
        data=replay(time=21);data['entities'][0]['blood']=1000;data['entities'][1]['blood']=499
        prior=dict(active=True,seen=NOW.timestamp(),sent=NOW.timestamp(),level=3)
        self.alerts.saved_state=dict(signature=self.alerts.signature(self.alerts.config),session=[data['filename'],data['recorded_at'],OWNER,1],time_seconds=1,
            targets={'larger|steam:'+OTHER:dict(prior),'target_low_blood|steam:'+OTHER:dict(prior)})
        self.evaluate(data);self.send.assert_called_once()
        self.assertIn('BLOOD MỤC TIÊU',self.send.call_args.args[2]);self.assertNotIn('LỚN HƠN',self.send.call_args.args[2])

    def test_pre_blood_encounters_keep_their_delivered_levels(self):
        data=replay(time=21)
        self.alerts.saved_state=dict(signature=self.alerts.signature({k:self.alerts.config[k] for k in alerts.PRE_BLOOD_KEYS}),
            session=[data['filename'],data['recorded_at'],OWNER,1],time_seconds=1,
            targets={'larger|steam:'+OTHER:dict(active=True,seen=NOW.timestamp(),sent=NOW.timestamp(),level=1)})
        self.evaluate(data);self.send.assert_not_called()

    def test_hp_comparison_uses_owners_current_hp_rather_than_their_maximum(self):
        data = replay();data['entities'][0].update(health=100, max_health=1000)
        data['entities'][1].update(health=100, max_health=900)
        self.evaluate(data);self.send.assert_not_called()
        data['entities'][0]['health'] = 300;data['time_seconds'] = 21
        self.evaluate(data, NOW + dt.timedelta(seconds=20))
        self.send.assert_called_once()

    def test_legacy_size_encounters_are_migrated_without_repeating_delivered_alerts(self):
        data = replay(time=21)
        self.alerts.saved_state = dict(signature=self.alerts.signature({k:self.alerts.config[k] for k in alerts.LEGACY_KEYS}),
            session=[data['filename'], data['recorded_at'], OWNER, 1], time_seconds=1,
            targets={'steam:'+OTHER:dict(active=True, seen=NOW.timestamp(), sent=NOW.timestamp(), level=1)})
        self.evaluate(data)
        self.send.assert_not_called()
        self.assertIn('larger|steam:'+OTHER, self.alerts.saved_state['targets'])

    def test_only_targets_included_in_a_bounded_message_are_marked_as_delivered(self):
        data = replay(entities=[entity(1, OWNER, 1000, 100000)] +
                      [entity(i+2, str(76561198000000100+i), 1100, 101000+i*100) for i in range(20)])
        self.evaluate(data)
        self.send.assert_called_once()
        text = self.send.call_args.args[2]
        self.assertLessEqual(len(text), 4000)
        delivered = sum('sent' in value for value in self.alerts.saved_state['targets'].values())
        self.assertEqual(delivered, text.count('🦖 Synthetic'))
        self.assertGreater(delivered, 0);self.assertLess(delivered, 20)
        data['time_seconds'] = 21
        self.evaluate(data, NOW + dt.timedelta(seconds=20))
        self.assertEqual(self.send.call_count, 2)


class TransportTests(unittest.TestCase):
    def test_optional_coordinates_compass_and_observation_age(self):
        data = replay(time=100)
        owner, target = data['entities']
        target.update(x=110000, y=90000, health_seen=40, stamina_seen=90, last_seen=80, growth=None)
        event = (target, math.hypot(100,100), 3, ['larger'], ['larger|target'])
        text, _ = alerts.alert_message(owner, [event], data, 12, {**alerts.DEFAULTS,'include_coordinates':True})
        for expected in ['Đông Bắc', '45°', 'vị trí 20s', 'HP 60s', 'stamina 10s', '📍 X', 'Y', 'trưởng thành chưa rõ']:
            self.assertIn(expected, text)

    def test_rich_text_payload_is_bounded_plain_text_without_player_identifiers(self):
        data = replay()
        data['entities'][1].update(growth=.85, stamina=35, max_stamina=100, health_seen=0, stamina_seen=0)
        text, included = alerts.alert_message(data['entities'][0], [(data['entities'][1], 1000, 1, ['larger'], ['larger|target'])], data, 5, alerts.DEFAULTS)
        response = io.BytesIO(b'{"ok":true}')
        with patch('telegram_alerts.urllib.request.urlopen', return_value=response) as opening:
            self.assertTrue(alerts.send_message(TOKEN, '12345', text)[0])
            request = opening.call_args.args[0]
            self.assertEqual(json.loads(request.data), {'chat_id': '12345', 'text': text})
            self.assertEqual(request.method, 'POST')
        self.assertEqual(included, ['larger|target'])
        for expected in ['Synthetic', '85%', '1.10×', '35 / 100 (35%)', 'Đông', 'HP', 'nguồn'.capitalize()]:
            self.assertIn(expected, text)
        self.assertNotIn(OWNER, text);self.assertNotIn(OTHER, text);self.assertNotIn('synthetic.replay', text)
        self.assertNotIn('📍', text)
        with self.assertRaises(ValueError):alerts.send_message(TOKEN, '12345', 'X=123 Y=456')
        with self.assertRaises(ValueError):alerts.send_message(TOKEN, '12345', alerts.ALERT_PREFIX + 'x'*4000)

    def test_error_messages_never_echo_token_and_honor_rate_limit(self):
        with patch('telegram_alerts.urllib.request.urlopen', side_effect=urllib.error.URLError('secret ' + TOKEN)):
            ok, error, delay = alerts.send_message(TOKEN, '12345', alerts.TEST_TEXT)
            self.assertFalse(ok);self.assertNotIn(TOKEN, error)
        error = urllib.error.HTTPError('secret ' + TOKEN, 429, 'Too many requests', {}, io.BytesIO(b'{"parameters":{"retry_after":123}}'))
        with patch('telegram_alerts.urllib.request.urlopen', side_effect=error):
            ok, message, delay = alerts.send_message(TOKEN, '12345', alerts.TEST_TEXT)
            self.assertFalse(ok);self.assertEqual(delay, 123);self.assertNotIn(TOKEN, message)


class ConfigurationApiTests(unittest.TestCase):
    def test_interval_updates_and_telegram_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);source = root / 'source';source.mkdir()
            c = app.Collector(source, data_dir=root / 'data')
            app.save_player_profile(c.data_dir, dict(steam_id='', name=''))
            server = app.LocalServer(('127.0.0.1', 0), app.Handler);server.collector = c
            thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
            def post(path, data):
                req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}' + path,
                    data=json.dumps(data).encode(), headers={'Content-Type':'application/json','X-Isle-Client':'1'}, method='POST')
                return json.load(urllib.request.urlopen(req, timeout=3))
            try:
                self.assertEqual(c.interval, 20)
                post('/api/config', dict(source_dir=str(source), interval_seconds=20))
                self.assertEqual(c.state()['interval_seconds'], 20)
                self.assertEqual(json.loads((c.data_dir/'config.json').read_text())['interval_seconds'], 20)
                with self.assertRaises(urllib.error.HTTPError):post('/api/config', dict(source_dir=str(source), interval_seconds=4))
                with self.assertRaises(urllib.error.HTTPError):post('/api/telegram', dict(enabled=True, bot_token=TOKEN, chat_id='12345'))
                app.save_player_profile(c.data_dir, dict(steam_id=OWNER, name='Synthetic'))
                result = post('/api/telegram', dict(enabled=True, bot_token=TOKEN, chat_id='12345', radius_m=1000, min_size_ratio=1.1))
                self.assertTrue(result['token_configured']);self.assertNotIn(TOKEN, json.dumps(c.state()))
                with patch('telegram_alerts.send_message', return_value=(True, '', 0)):
                    self.assertTrue(post('/api/telegram/test', {})['ok'])
            finally:
                server.shutdown();thread.join();server.server_close();c.telegram.close()


if __name__ == '__main__':unittest.main()
