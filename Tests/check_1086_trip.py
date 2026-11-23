"""Check evidence from a Windows AT-regression run. Use UE's bundled Python or Python 3."""
import argparse
import csv
import math
from pathlib import Path


def observations(rows):
    at = [r for r in rows if r['mode'] == 'AT (1086)']
    checks = dict.fromkeys(('neutral_park', 'drive', 'turn_under_steer', 'brake_then_stop',
                            'front_door_cycle', 'middle_door_cycle', 'headlights', 'signals',
                            'camera', 'valid_wheel_samples', 'fault_free'), False)
    moved = braking = False
    previous = None
    max_speed = 0
    opened = set()
    lights, turns, cameras = set(), set(), set()
    for r in at:
        speed = float(r['speed_m_s'])
        if not math.isfinite(speed):
            raise ValueError('non-finite speed in recording')
        gear = int(r['gear'])
        checks['neutral_park'] |= gear == 0 and r['park'] == '1' and abs(speed) < .22
        moved |= speed > 1.0 and gear > 0 and float(r['rt']) > .05 and r['park'] == '0'
        checks['drive'] |= moved
        if previous:
            dt = float(r['time_s']) - float(previous['time_s'])
            yaw_delta = (float(r['yaw_deg']) - float(previous['yaw_deg']) + 180) % 360 - 180
            checks['turn_under_steer'] |= (0 < dt < .2 and abs(float(r['steer'])) > .15
                                            and abs(speed) > .5 and abs(yaw_delta) > .015)
            if moved and float(r['brake']) > .2 and speed < float(previous['speed_m_s']):
                braking = True
        checks['brake_then_stop'] |= braking and max_speed > 1 and abs(speed) < .22
        max_speed = max(speed,max_speed)
        for col in ('front_door','middle_door'):
            if float(r[col]) >= .98: opened.add(col)
            checks[col+'_cycle'] |= col in opened and float(r[col]) < .02
        lights.add(r['lights']); turns.add(r['turn']); cameras.add(r['cab'])
        checks['valid_wheel_samples'] |= all(r[w+'_drive_nm'] != '' and r[w+'_brake_nm'] != ''
                                             for w in ('fl','fr','rl','rr'))
        previous = r
    checks.update(headlights={'0','1'} <= lights, signals={'-1','1'} <= turns,
                  camera={'0','1'} <= cameras, fault_free=bool(at) and all(r['fault']=='0' for r in at))
    return checks


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_file', type=Path)
    args = parser.parse_args()
    with args.csv_file.open(encoding='utf-8-sig',newline='') as f:
        result = observations(csv.DictReader(f))
    for name, seen in result.items():
        print(f"{'OK' if seen else 'NO EVIDENCE'}  {name}")
    raise SystemExit(0 if all(result.values()) else 1)
