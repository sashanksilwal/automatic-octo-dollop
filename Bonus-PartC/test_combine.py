import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('combine',Path(__file__).with_name('combine.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


class CombineTests(unittest.TestCase):
    def batch(self,root,name,source,duration,count,pipeline):
        base=root/name;run=base/'run-001';run.mkdir(parents=True)
        (base/'batch.json').write_text(json.dumps({'network':'test-network','scenario':'stationary','variant':'baseline','settings':{'fps':8}}))
        with (run/'inference.jsonl').open('w') as out:
            for i in range(count):out.write(json.dumps({'source_session':source,'sequence':i,'pipeline_ms':pipeline,'local_receive_to_result_ms':pipeline+5,'faces':[{}]})+'\n')
        row={'run_id':'run-001','source_session':source,'duration_s':duration,'inferred_frames':count,'laptop_received_frames':count,
             'actual_inference_fps':count/duration,'pipeline_ms':{'p95':pipeline},'laptop_silence_over_500_ms':0,'laptop_max_silence_s':.1}
        return {'batch':str(base),'network':'test-network','scenario':'stationary','variant':'baseline','runs':[row]}

    def test_actual_counts_time_weighting_and_duplicate_session_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            a=self.batch(root,'a','camera-a',2,2,10)
            b=self.batch(root,'b','camera-b',8,4,30)
            merged=c.combine([a,b])
            self.assertEqual(merged['complete_runs'],2)
            self.assertEqual(merged['total_measured_s'],10)
            self.assertEqual(merged['actual_inference_fps_pooled'],.6)
            self.assertAlmostEqual(merged['pipeline_ms']['mean'],(2*10+4*30)/6)
            self.assertNotEqual(merged['runs'][0]['run_id'],merged['runs'][1]['run_id'])
            with self.assertRaises(ValueError):c.combine([a,a])


if __name__=='__main__':unittest.main()
