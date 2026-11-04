import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('analysis',Path(__file__).with_name('analyze.py'))
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)

class AnalysisTests(unittest.TestCase):
    def test_empty_and_interpolated_percentiles(self):
        self.assertIsNone(a.percentile([],.95))
        self.assertEqual(a.percentile([10,20],.95),19.5)
        self.assertEqual(a.distribution([None,float('nan'),7])['n'],1)

    def test_sequence_join_clock_isolation_and_boundary_stalls(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);source='camera-1'
            (p/'manifest.json').write_text(json.dumps({'status':'complete','source_session':source,
                'network':'PAL3.0','scenario':'stationary','measured_duration_s':2,
                'measurement_start_mono_ns':0,'measurement_end_mono_ns':2_000_000_000,
                'device_start':{},'device_end':{}}))
            fields=['event','source_session','sequence','local_mono_ns','capture_mono_ns','jpeg_bytes']
            for role,offset,seqs in [('glasses',90_000_000_000,[0,1,2]),('phone',800_000_000_000,[0,2]),('laptop',0,[0,2])]:
                with (p/(role+'.csv')).open('w',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
                    for seq in seqs:
                        w.writerow(dict(event='frame_received',source_session=source,sequence=seq,
                            local_mono_ns=offset+100_000_000+seq*100_000_000,
                            capture_mono_ns=50_000_000_000+seq*100_000_000,jpeg_bytes=100))
            inference={'source_session':source,'sequence':0,'published':True,'pipeline_ms':140,
                       'worker_ms':142,'local_receive_to_result_ms':150,'detection_ms':40,
                       'gaze_and_overlay_ms':100,'faces':[{}]}
            (p/'inference.jsonl').write_text(json.dumps(inference)+'\n')
            (p/'rtt.jsonl').write_text(json.dumps({'rtt_ms':None})+'\n')
            (p/'samples.jsonl').write_text(json.dumps({'stream':{'state':'streaming'}})+'\n')
            result=a.analyze_run(p)
            self.assertEqual(result['actual_inference_fps'],.5)
            self.assertEqual(result['actual_laptop_receive_fps'],1)
            self.assertEqual(result['source_capture_fps_matched_interval'],10)
            self.assertEqual(result['phone_receive_fps_matched_interval'],5)
            self.assertEqual(result['source_frames_missing_at_phone_in_matched_interval'],1)
            self.assertEqual(result['phone_frames_missing_at_laptop_in_matched_interval'],0)
            self.assertEqual(result['pipeline_over_125_ms'],1)
            self.assertEqual(result['laptop_silence_over_500_ms'],1)
            self.assertEqual(result['laptop_max_silence_s'],1.7)
            self.assertEqual(result['ping_failed_probes'],1)
            self.assertEqual(result['local_receive_to_result_ms']['mean'],150)

    def test_incomplete_run_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'manifest.json').write_text('{"status":"measuring"}')
            self.assertIsNone(a.analyze_run(p))

if __name__=='__main__':unittest.main()
