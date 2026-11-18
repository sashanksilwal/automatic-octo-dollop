"""Metric checks: matching, normalized distance, missing heads and inside/outside."""
import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'tools/evaluate_gaze_accuracy.py'
try:
    s=importlib.util.spec_from_file_location('accuracy',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
except ImportError:
    m=None

@unittest.skipIf(m is None,'Optional gaze/OpenCV environment required')
class AccuracyTests(unittest.TestCase):
    def label(self,box,gaze,inside=True):return dict(track='person.txt',head_bbox_pixels=box,gaze_pixels=gaze,inside=inside)
    def test_missing_head_penalizes_joint_success_and_coverage(self):
        frame=dict(key='show/clip/frame.jpg',labels=[self.label([0,0,20,20],[50,25]),self.label([50,50,80,80],[50,25])])
        face=dict(bbox=[0,0,20,20],in_frame_probability=.9,heatmap_peak_xy_normalized=[.5,.5])
        rows=m.score_frame(frame,dict(faces=[face]),100,50);result=m.metrics(rows)
        self.assertEqual(result['head_detection_recall'],.5)
        self.assertEqual(result['conditional_in_frame_normalized_l2']['mean'],0)
        self.assertEqual(result['joint_in_frame_success_at_0_1'],.5)
    def test_out_prediction_keeps_peak_error_but_fails_joint_target(self):
        frame=dict(key='show/clip/frame.jpg',labels=[self.label([0,0,20,20],[50,25])])
        face=dict(bbox=[0,0,20,20],in_frame_probability=.79,heatmap_peak_xy_normalized=[.5,.5])
        row=m.score_frame(frame,dict(faces=[face]),100,50)[0]
        self.assertEqual(row['normalized_l2'],0)
        self.assertFalse(row['joint_success_at_0.1'])
        self.assertFalse(row['inout_correct'])
    def test_one_prediction_cannot_match_two_people(self):
        labels=[self.label([0,0,20,20],[0,0]),self.label([1,1,21,21],[0,0])]
        self.assertEqual(len(m.match_heads(labels,[dict(bbox=[0,0,20,20])])),1)
    def test_out_of_frame_has_no_target_distance(self):
        frame=dict(key='show/clip/frame.jpg',labels=[self.label([0,0,20,20],[-1,-1],False)])
        rows=m.score_frame(frame,dict(faces=[dict(bbox=[0,0,20,20],in_frame_probability=.1,heatmap_peak_xy_normalized=[.5,.5])]),100,50)
        self.assertTrue(rows[0]['inout_correct']);self.assertNotIn('normalized_l2',rows[0])
        self.assertIsNone(m.metrics(rows)['joint_in_frame_success_at_0_1'])
if __name__=='__main__':unittest.main()
