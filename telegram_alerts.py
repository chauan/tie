"""Evaluate replay encounters and send the dinosaur details selected by the user."""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import urllib.error
import urllib.request
import uuid

DEFAULTS = dict(enabled=False, bot_token="", chat_id="", radius_m=1000,
                min_size_ratio=1.1, cooldown_seconds=120, friend_ids=[],
                alert_larger=True, alert_low_health=True, low_health_ratio=0.5,
                include_coordinates=False, alert_own_low_blood=False,
                alert_target_low_blood=True, low_blood_ratio=0.5)
LEGACY_KEYS = ("enabled", "bot_token", "chat_id", "radius_m", "min_size_ratio", "cooldown_seconds", "friend_ids")
PRE_BLOOD_KEYS = LEGACY_KEYS + ("alert_larger", "alert_low_health", "low_health_ratio", "include_coordinates")
ALERT_PREFIX = "🦖 Replay Radar\n"
TEST_TEXT = "Replay Radar: kết nối Telegram hoạt động. Đây là tin nhắn thử."


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def active(entity):
    return (entity.get("in_scope") is True and entity.get("dead") is not True
            and entity.get("health") != 0
            and all(number(entity.get(k)) for k in ("x", "y", "z"))
            and any(entity[k] != 0 for k in ("x", "y", "z")))


def estimated_weight(entity):
    value = entity.get("max_health")
    return value if ("/Characters/Dinosaurs/" in str(entity.get("class_path", ""))
                     and number(value) and value > 0) else None


def same_group(a, b):
    group = a.get("group_id")
    return type(group) is int and group != 0 and type(b.get("group_id")) is int and group == b["group_id"]


def observed_value(entity, field):
    value = entity.get(field)
    return value if number(value) and value >= 0 else None


def vital_text(entity, field, maximum):
    value, limit = observed_value(entity, field), observed_value(entity, maximum)
    if value is None:
        return "chưa rõ"
    return f"{value:,.0f} / {limit:,.0f} ({value / limit * 100:.0f}%)" if limit and limit > 0 else f"{value:,.0f} (tối đa chưa rõ)"


def observation_age(replay_time, seen):
    return f"{max(0, replay_time - seen):.0f}s" if number(seen) and seen >= 0 else "chưa rõ"


def alert_message(owner, events, replay, source_age, config):
    """Pack complete target descriptions; return only the encounter keys included."""
    own_health = observed_value(owner, "health")
    own_blood = observed_value(owner, "blood")
    own_weight = estimated_weight(owner)
    header = ALERT_PREFIX + f"Bạn: HP {vital_text(owner, 'health', 'max_health')} · Blood {vital_text(owner, 'blood', 'max_blood')}"
    if own_weight:
        header += f" · ~{own_weight:,.0f} kg (ước tính)"
    text, included = header + "\n", []
    for event in events:
        target, distance, level, reasons, keys = event
        labels = []
        if "larger" in reasons:
            labels.append(f"⚠ LỚN HƠN ≥{(config['min_size_ratio'] - 1) * 100:g}%")
        if "low_health" in reasons:
            labels.append(f"🩸 HP MỤC TIÊU <{config['low_health_ratio'] * 100:g}% HP CỦA BẠN")
        if "own_low_blood" in reasons:
            labels.append(f"🩸 BLOOD CỦA BẠN <{config['low_blood_ratio'] * 100:g}%")
        if "target_low_blood" in reasons:
            labels.append(f"🩸 BLOOD MỤC TIÊU <{config['low_blood_ratio'] * 100:g}% BLOOD CỦA BẠN")
        species = " ".join(str(target.get("species") or "Dino chưa rõ loài").split())[:80]
        growth = target.get("growth")
        growth_text = f"{growth * 100:.0f}%" if number(growth) and 0 <= growth <= 1 else "chưa rõ"
        if distance < 0.001:
            direction = "cùng vị trí"
        else:
            bearing = (math.degrees(math.atan2(target['x'] - owner['x'], owner['y'] - target['y'])) + 360) % 360
            compass = ["Bắc", "Đông Bắc", "Đông", "Đông Nam", "Nam", "Tây Nam", "Tây", "Tây Bắc"]
            direction = f"{compass[int((bearing + 22.5) // 45) % 8]} · {bearing:.0f}°"
        weight = estimated_weight(target)
        size = f"{weight / own_weight:.2f}× bạn (~{weight:,.0f} kg)" if weight and own_weight else "chưa rõ"
        health = observed_value(target, "health")
        relative_hp = f" · {health / own_health * 100:.1f}% HP của bạn" if health is not None and own_health and own_health > 0 else ""
        band = config['radius_m'] / (4 if level == 3 else 2 if level == 2 else 1)
        own_alert = "own_low_blood" in reasons
        blood = observed_value(target, "blood")
        relative_blood = f" · {blood / own_blood * 100:.1f}% Blood của bạn" if not own_alert and blood is not None and own_blood and own_blood > 0 else ""
        if own_alert:
            relative_hp = ""
        block = ("\n" + " · ".join(labels) + f"\n🦖 {species} · trưởng thành {growth_text}"
                 + ("\nDino của bạn" if own_alert else f"\n📏 {distance:,.0f} m · {direction} · mức gần {band:g} m")
                 + ("" if own_alert else f"\n⚖ Kích thước ước tính: {size}")
                 + f"\n❤️ HP: {vital_text(target, 'health', 'max_health')}{relative_hp}"
                 + f"\n🩸 Blood: {vital_text(target, 'blood', 'max_blood')}{relative_blood}"
                 + f"\n⚡ Stamina: {vital_text(target, 'stamina', 'max_stamina')}"
                 + f"\n🕒 Tuổi quan sát trước mốc cuối replay: vị trí {observation_age(replay['time_seconds'], target.get('last_seen'))}"
                 + f" · HP {observation_age(replay['time_seconds'], target.get('health_seen'))}"
                 + f" · Blood {observation_age(replay['time_seconds'], target.get('blood_seen'))}"
                 + f" · stamina {observation_age(replay['time_seconds'], target.get('stamina_seen'))}\n")
        if config["include_coordinates"]:
            block += f"📍 X {target['x']:,.0f} / Y {target['y']:,.0f} cm\n"
        # Leave room for the source-age and omitted-target notices. Never cut a target's description.
        if len(text) + len(block) > 3650:
            break
        text += block
        included.extend(keys)
    if len(included) < sum(len(event[4]) for event in events):
        text += "\nCòn mục tiêu đạt ngưỡng; service sẽ kiểm tra tiếp ở bản replay mới.\n"
    text += f"\nNguồn file cập nhật {max(0, source_age):.0f}s trước. Kích thước ước tính từ HP tối đa."
    return text, included


def send_message(token, chat_id, text):
    """Send a bounded alert description or the explicit test message."""
    if not isinstance(text, str) or len(text) > 4000 or not (text == TEST_TEXT or text.startswith(ALERT_PREFIX)):
        raise ValueError("Tin Telegram cần là cảnh báo dino hoặc tin thử, tối đa 4.000 ký tự.")
    request = urllib.request.Request(
        "https://api.telegram.org/bot" + token + "/sendMessage",
        data=json.dumps(dict(chat_id=chat_id, text=text)).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            result = json.load(response)
        return (True, "", 0) if result.get("ok") is True else (False, "Telegram không nhận tin nhắn.", 60)
    except urllib.error.HTTPError as error:
        delay = 60
        if error.code == 429:
            try:
                delay = max(1, min(3600, int(json.load(error).get("parameters", {}).get("retry_after", 60))))
            except (ValueError, TypeError, OSError):
                pass
        return False, f"Telegram trả mã {error.code}. Kiểm tra Bot Token, Chat ID và quyền gửi tin.", delay
    except (OSError, ValueError, TimeoutError):
        # urllib exceptions can contain the secret URL; don't return or log them.
        return False, "Chưa kết nối được Telegram. Service sẽ thử lại ở bản replay mới.", 60


class TelegramAlerts:
    def __init__(self, data_dir):
        self.config_path = Path(data_dir) / "telegram.json"
        self.state_path = Path(data_dir) / "telegram-state.json"
        self.lock = threading.RLock()
        self.config = copy.deepcopy(DEFAULTS)
        self.saved_state = {}
        self.status = dict(message="Chưa bật Telegram.", last_sent_at=None, error=None)
        try:
            if self.config_path.exists():
                self.config = self.validate(json.loads(self.config_path.read_text(encoding="utf-8")))
            if self.state_path.exists():
                self.saved_state = json.loads(self.state_path.read_text(encoding="utf-8"))
                if not isinstance(self.saved_state, dict):
                    self.saved_state = {}
            if self.config["enabled"]:
                self.status["message"] = "Đợi bản replay mới để kiểm tra điều kiện cảnh báo."
        except (ValueError, TypeError, OSError, AttributeError):
            self.config = copy.deepcopy(DEFAULTS)
            self.saved_state = {}
            self.status["error"] = "Cấu hình Telegram không hợp lệ; cảnh báo đang tắt."
        self.pending = None
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.thread = None
        self.retry_at = 0

    @staticmethod
    def validate(value):
        config = {**copy.deepcopy(DEFAULTS), **{k: v for k, v in value.items() if k in DEFAULTS}}
        if type(config["enabled"]) is not bool:
            raise ValueError("Trạng thái Telegram phải là bật hoặc tắt.")
        token, chat = config["bot_token"], config["chat_id"]
        if not isinstance(token, str) or token and not re.fullmatch(r"[0-9]{5,20}:[A-Za-z0-9_-]{20,140}", token):
            raise ValueError("Bot Token không đúng định dạng.")
        if not isinstance(chat, str) or chat and not re.fullmatch(r"-?[0-9]{1,20}", chat):
            raise ValueError("Chat ID cần là số của cuộc trò chuyện Telegram.")
        if config["enabled"] and (not token or not chat):
            raise ValueError("Nhập Bot Token và Chat ID trước khi bật Telegram.")
        if not number(config["radius_m"]) or not 10 <= config["radius_m"] <= 5000:
            raise ValueError("Bán kính Telegram phải từ 10 đến 5.000 m.")
        if not number(config["min_size_ratio"]) or not 1 <= config["min_size_ratio"] <= 10:
            raise ValueError("Ngưỡng lớn hơn phải từ 0% đến 900%.")
        for flag in ("alert_larger", "alert_low_health", "include_coordinates", "alert_own_low_blood", "alert_target_low_blood"):
            if type(config[flag]) is not bool:
                raise ValueError("Loại cảnh báo và tùy chọn tọa độ phải là bật hoặc tắt.")
        if config["enabled"] and not any(config[k] for k in ("alert_larger","alert_low_health","alert_own_low_blood","alert_target_low_blood")):
            raise ValueError("Chọn ít nhất một loại cảnh báo Telegram.")
        if not number(config["low_health_ratio"]) or not 0 < config["low_health_ratio"] <= 1:
            raise ValueError("Ngưỡng HP mục tiêu cần lớn hơn 0% và không quá 100% HP hiện tại của bạn.")
        if not number(config["low_blood_ratio"]) or not 0 < config["low_blood_ratio"] <= 1:
            raise ValueError("Ngưỡng Blood cần lớn hơn 0% và không quá 100% Blood hiện tại của bạn.")
        if type(config["cooldown_seconds"]) is not int or not 30 <= config["cooldown_seconds"] <= 3600:
            raise ValueError("Thời gian chống lặp phải từ 30 đến 3.600 giây.")
        friends = config["friend_ids"]
        if not isinstance(friends, list) or len(friends) > 100 or any(not isinstance(x, str) or not re.fullmatch(r"[0-9]{17}", x) for x in friends):
            raise ValueError("Danh sách bỏ qua cần tối đa 100 SteamID, mỗi ID đủ 17 chữ số.")
        config["friend_ids"] = sorted(set(friends))
        return config

    def public(self):
        with self.lock:
            return {**{k: v for k, v in self.config.items() if k != "bot_token"},
                    "token_configured": bool(self.config["bot_token"]), "target_blood_basis": "owner_current", "status": dict(self.status)}

    def configure(self, body):
        with self.lock:
            updates = {k: v for k, v in body.items() if k in DEFAULTS}
            if updates.get("bot_token") == "":
                updates.pop("bot_token")
            config = self.validate({**self.config, **updates})
            if config != self.config:
                write_json(self.config_path, config)
                write_json(self.state_path, {})
                self.config, self.saved_state, self.pending = config, {}, None
                self.retry_at = 0
                self.status.update(message="Đợi bản replay mới." if config["enabled"] else "Đã tắt Telegram.", error=None)
            return self.public()

    @staticmethod
    def signature(config):
        return hashlib.sha256(json.dumps(config, sort_keys=True).encode("utf-8")).hexdigest()

    def submit(self, replay, profile):
        with self.lock:
            if not self.config["enabled"]:
                return
            self.pending = ({k: replay.get(k) for k in ("entities", "time_seconds", "filename", "recorded_at", "source_modified_at", "copied_at")}, dict(profile))
        self.wake.set()

    def process(self, replay, profile, now=None):
        """All identity, size and position checks run locally on a new snapshot."""
        now = now or dt.datetime.now(dt.timezone.utc)
        timestamp = now.timestamp()
        with self.lock:
            config, saved = copy.deepcopy(self.config), copy.deepcopy(self.saved_state)
        if not config["enabled"] or timestamp < self.retry_at:
            return
        signature = self.signature(config)
        try:
            modified = dt.datetime.fromisoformat(replay.get("source_modified_at") or replay["copied_at"])
            source_age = (now - modified).total_seconds()
            if not -60 <= source_age <= 90:
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            with self.lock:
                self.status["message"] = "Tạm dừng cảnh báo: replay nguồn đã cũ hoặc chưa rõ thời gian."
            return
        entities = replay.get("entities") or []
        owners = [e for e in entities if profile.get("steam_id") and e.get("steam_id") == profile["steam_id"]]
        owner = max(owners, key=lambda e: e.get("last_seen") or 0) if owners else None
        own_weight = estimated_weight(owner) if owner and active(owner) else None
        own_health = observed_value(owner, "health") if owner and active(owner) else None
        own_blood = observed_value(owner, "blood") if owner and active(owner) else None
        own_max_blood = observed_value(owner, "max_blood") if owner and active(owner) else None
        if not owner or not active(owner) or not (
                config["alert_larger"] and own_weight is not None
                or config["alert_low_health"] and own_health is not None and own_health > 0
                or config["alert_target_low_blood"] and own_blood is not None and own_blood > 0
                or config["alert_own_low_blood"] and own_blood is not None and own_max_blood is not None and own_max_blood > 0):
            with self.lock:
                self.status["message"] = "Tạm dừng: chưa có dino đang sống, vị trí hoặc chỉ số cần so sánh của bạn."
            return
        session = [replay.get("filename"), replay.get("recorded_at"), profile["steam_id"], owner.get("id")]
        # Preserve already delivered size alerts when upgrading the old encounter format.
        legacy_signature = self.signature({k: config[k] for k in LEGACY_KEYS})
        if saved.get("signature") == legacy_signature and saved.get("session") == session:
            saved.update(signature=signature, targets={"larger|" + k: v for k, v in saved.get("targets", {}).items()})
        elif saved.get("signature") == self.signature({k:config[k] for k in PRE_BLOOD_KEYS}) and saved.get("session") == session:
            saved["signature"] = signature
        if saved.get("signature") != signature or saved.get("session") != session:
            saved = dict(signature=signature, session=session, targets={}, time_seconds=-1)
        if saved.get("blood_basis") != "owner_current":
            saved["targets"] = {k:v for k,v in saved.get("targets", {}).items() if not k.startswith("target_low_blood|")}
            saved["blood_basis"] = "owner_current"
        replay_time = replay.get("time_seconds")
        if not number(replay_time) or replay_time <= saved.get("time_seconds", -1):
            return
        previous = saved.get("targets", {})
        current = {key: {**value, "active": False} for key, value in previous.items() if timestamp - value.get("seen", 0) <= 86400}
        candidates, latest = {}, {}
        own_level = None
        if (config["alert_own_low_blood"] and own_blood is not None and own_max_blood and own_max_blood > 0
                and own_blood / own_max_blood < config["low_blood_ratio"]):
            fraction = own_blood / own_max_blood
            own_level = 3 if fraction <= config["low_blood_ratio"] / 4 else 2 if fraction <= config["low_blood_ratio"] / 2 else 1
            candidates["own:"+profile["steam_id"]] = (owner, 0, ["own_low_blood"])
        for entity in entities:
            identity = "steam:" + entity["steam_id"] if entity.get("steam_id") else "actor:" + str(entity.get("id"))
            if identity not in latest or (entity.get("last_seen") or 0) > (latest[identity].get("last_seen") or 0):
                latest[identity] = entity
        for identity, entity in latest.items():
            if entity.get("steam_id") == profile["steam_id"] or entity.get("id") == owner.get("id") or entity.get("steam_id") in config["friend_ids"]:
                continue
            if same_group(owner, entity):
                continue
            if entity.get("kind") not in ("player", "ai") or not active(entity):
                continue
            if "/Characters/Dinosaurs/" not in str(entity.get("class_path", "")):
                continue
            weight = estimated_weight(entity)
            health = observed_value(entity, "health")
            reasons = []
            if (config["alert_larger"] and weight is not None and own_weight is not None
                    and weight > own_weight and weight / own_weight + 1e-9 >= config["min_size_ratio"]):
                reasons.append("larger")
            if (config["alert_low_health"] and health is not None and health > 0
                    and own_health is not None and own_health > 0
                    and health / own_health < config["low_health_ratio"]):
                reasons.append("low_health")
            blood = observed_value(entity, "blood")
            if (config["alert_target_low_blood"] and blood is not None and own_blood is not None and own_blood > 0
                    and blood / own_blood < config["low_blood_ratio"]):
                reasons.append("target_low_blood")
            if not reasons:
                continue
            distance = math.hypot(entity["x"] - owner["x"], entity["y"] - owner["y"]) / 100
            if distance > config["radius_m"]:
                continue
            candidates[identity] = (entity, distance, reasons)
        pending = []
        for identity, (entity, distance, reasons) in candidates.items():
            level = 3 if distance <= config["radius_m"] / 4 else 2 if distance <= config["radius_m"] / 2 else 1
            if identity.startswith("own:"):
                level = own_level
            due_reasons, due_keys = [], []
            for reason in reasons:
                key = reason + "|" + identity
                before = previous.get(key, {})
                reentered = not before.get("active") and timestamp - before.get("sent", 0) >= config["cooldown_seconds"]
                current[key] = {**before, "active": True, "seen": timestamp}
                if not before or level > before.get("level", 0) or reentered:
                    due_reasons.append(reason)
                    due_keys.append(key)
            if due_keys:
                pending.append((entity, distance, level, due_reasons, due_keys))
        pending.sort(key=lambda event: (-event[2], event[1]))
        if pending:
            with self.lock:
                if self.signature(self.config) != signature:
                    return
            text, included = alert_message(owner, pending, replay, source_age, config)
            ok, error, delay = send_message(config["bot_token"], config["chat_id"], text)
            with self.lock:
                if self.signature(self.config) != signature:
                    return
                self.status.update(error=None if ok else error, message="Đã gửi cảnh báo Telegram." if ok else "Gửi Telegram chưa thành công.")
                if ok:
                    self.status["last_sent_at"] = now.isoformat()
                else:
                    self.retry_at = timestamp + delay
            if ok:
                levels = {key: event[2] for event in pending for key in event[4]}
                for key in included:
                    current[key].update(level=max(levels[key], previous.get(key, {}).get("level", 0)), sent=timestamp)
        else:
            with self.lock:
                self.status["message"] = "Đang theo dõi; chưa có cảnh báo mới đạt ngưỡng."
        saved.update(targets=current, time_seconds=replay_time)
        with self.lock:
            if self.signature(self.config) == signature:
                write_json(self.state_path, saved)
                self.saved_state = saved

    def test(self):
        with self.lock:
            config = dict(self.config)
        if not config["bot_token"] or not config["chat_id"]:
            raise ValueError("Lưu Bot Token và Chat ID trước khi gửi thử.")
        ok, error, _ = send_message(config["bot_token"], config["chat_id"], TEST_TEXT)
        if not ok:
            raise ValueError(error)
        return {"ok": True}

    def start(self):
        def work():
            while not self.stop.is_set():
                self.wake.wait(1)
                self.wake.clear()
                if self.stop.is_set():
                    break
                with self.lock:
                    pending, self.pending = self.pending, None
                if pending:
                    try:
                        self.process(*pending)
                    except Exception:
                        with self.lock:
                            self.status.update(error="Chưa xử lý được cảnh báo Telegram; đồng bộ replay vẫn tiếp tục.")
        self.thread = threading.Thread(target=work, name="telegram-alerts", daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=10)
