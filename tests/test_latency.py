import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

try:
    import cv2
    import numpy as np
    spec=importlib.util.spec_from_file_location('latency',Path(__file__).resolve().parents[1]/'tools/latency_probe.py')
    latency=importlib.util.module_from_spec(spec);spec.loader.exec_module(latency)
except ImportError:
    latency=None


@unittest.skipIf(latency is None,'Optional gaze/OpenCV environment required')
class OpticalAnalysisTests(unittest.TestCase):
    def test_known_optical_marker_age_and_wrap_in_encoded_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);video=root/'synthetic.avi'
            writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'MJPG'),30,(560,280))
            self.assertTrue(writer.isOpened())
            for i in range(30):
                source=(10+i*2)%1000;received=(source-25)%1000
                image=np.full((280,560,3),255,np.uint8)
                for offset,marker_id in [(0,source),(280,received)]:
                    code=cv2.aruco.generateImageMarker(latency.DICTIONARY,marker_id,240)
                    image[20:260,offset+20:offset+260]=cv2.cvtColor(code,cv2.COLOR_GRAY2BGR)
                writer.write(image)
            writer.release()
            args=argparse.Namespace(video=video,source_roi=(0,0,280,280),received_roi=(280,0,280,280),sample_fps=10,output=root/'result')
            with contextlib.redirect_stdout(io.StringIO()):latency.analyze(args)
            result=json.loads((args.output/'summary.json').read_text())
            self.assertEqual(result['readable_pairs'],10)
            self.assertEqual(result['optical_display_age_ms']['mean'],500)
            self.assertEqual(result['optical_display_age_ms']['p95'],500)


if __name__=='__main__':unittest.main()
