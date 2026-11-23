"""Headless test of asset selection and AT telemetry checks (no Unreal asset serialization)."""
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from check_1086_trip import observations

ROOT = Path(__file__).resolve().parents[1]


class UpgradeTests(unittest.TestCase):
    def test_partial_and_fresh(self):
        mesh_type = type('SkeletalMesh', (), {'get_editor_property': lambda self, name: name == 'physics_asset'})
        mesh = mesh_type()
        with tempfile.TemporaryDirectory() as tmp:
            ue = SimpleNamespace(Paths=SimpleNamespace(project_dir=lambda:tmp, convert_relative_path_to_full=str),
                                 load_asset=Mock(return_value=mesh), SkeletalMesh=mesh_type)
            with patch.dict(sys.modules, unreal=ue):
                prepare = runpy.run_path(str(ROOT/'scripts/prepare_1086_upgrade.py'))['prepare']
            api = {k:Mock(return_value=k) for k in ('new_folder','create_driving_classes','create_yard','run')}
            with patch('runpy.run_path',return_value=api):
                self.assertEqual(prepare(),'run')
                f=Path(tmp)/'Content/Kotoden1086/Build_002/SK_Kotoden1086.uasset'
                f.parent.mkdir(parents=True); f.write_bytes(b'old')
                self.assertEqual(prepare(),'create_yard')
                api['create_driving_classes'].assert_called_once_with('new_folder',mesh)
                api['run'].assert_called_once()
                self.assertEqual(f.read_bytes(),b'old')

    def test_at_evidence(self):
        row = dict(mode='AT (1086)',speed_m_s='0',gear='0',park='1',rt='0',time_s='0',
                   yaw_deg='0',steer='0',brake='0',front_door='1',middle_door='1',lights='0',
                   turn='-1',cab='1',fault='0')
        for wheel in ('fl','fr','rl','rr'):
            for value in ('drive','brake'): row[f'{wheel}_{value}_nm']='0'
        moving=dict(row,speed_m_s='2',gear='1',park='0',rt='.5',time_s='.05',yaw_deg='1',
                    steer='.5',front_door='0',middle_door='0',lights='1',turn='1',cab='0')
        stop=dict(moving,speed_m_s='0',brake='1',time_s='.10')
        self.assertTrue(all(observations([row,moving,stop]).values()))
        self.assertFalse(observations([row,moving])['brake_then_stop'])
        self.assertFalse(observations([dict(row,fault='1')])['fault_free'])
        self.assertFalse(any(observations([dict(row,mode='Manual MT (fictional)')]).values()))


if __name__=='__main__':
    unittest.main()
