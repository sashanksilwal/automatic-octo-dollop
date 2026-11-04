"""Local MTGS static VSGaze adapter. See docs/PART_B.md for upstream licenses.

Uses the official MTGS architecture and strict checkpoint loading. Preprocessing
follows its demo; the static model needs no temporal tracker or future frames.
"""
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import torch
import torchvision.transforms.functional as TF
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT/'.tools/gaze-models/mtgs-static-vsgaze.ckpt'
HEAD_MODEL = ROOT/'.tools/gaze-models/crowdhuman_yolov5m.pt'


class MTGSEngine:
    def __init__(self, device='auto', image_size=448, precision='float32'):
        if image_size not in (224, 448) or precision not in ('float32', 'float16'):
            raise ValueError('Use scene size 224 or 448 and precision float32 or float16')
        sys.path[:0] = [str(ROOT/'.tools/MTGS'), str(ROOT/'.tools/dinov2'),
                        str(ROOT/'.tools/MTGS/mtgs/tools/yolov5crowdhuman')]
        os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'.tools/matplotlib'))
        from mtgs.networks.mtgs_net import MTGS
        from dinov2.hub.backbones import dinov2_vitb14
        from mtgs.tools.yolov5crowdhuman import letterbox, non_max_suppression, scale_coords
        from mtgs.utils import square_bbox
        self.letterbox, self.nms, self.scale_coords, self.square_bbox = letterbox, non_max_suppression, scale_coords, square_bbox
        self.device = ('mps' if torch.backends.mps.is_available() else 'cpu') if device == 'auto' else device
        self.image_size = image_size
        self.precision = precision
        self.dtype = torch.float16 if precision == 'float16' else torch.float32
        if precision == 'float16' and self.device != 'mps':
            raise ValueError('The float16 prototype currently requires the Apple MPS GPU')
        torch.set_num_threads(4)
        # Architecture only: every backbone weight comes from the MTGS checkpoint.
        backbone = dinov2_vitb14(pretrained=False)
        with patch('torch.hub.load', return_value=backbone):
            self.model = MTGS(image_size=448, patch_size=14, decoder_feature_dim=128,
                              decoder_use_bn=True, temporal_context=0)
        checkpoint = torch.load(MODEL, map_location='cpu', weights_only=False)
        state = {k.removeprefix('model.'):v for k,v in checkpoint['state_dict'].items()}
        self.model.load_state_dict(state, strict=True)
        del checkpoint, state
        self.model = self.model.to(device=self.device, dtype=self.dtype).eval()
        self.detector = torch.load(HEAD_MODEL, map_location='cpu', weights_only=False)['model'].float().fuse().eval()
        for module in self.detector.modules():
            if isinstance(module, torch.nn.Upsample):
                module.recompute_scale_factor = None
        self.detector = self.detector.to(self.device)
        self.mean, self.std = [.44232,.40506,.36457], [.28674,.27776,.27995]

    def sync(self):
        if self.device == 'mps':
            torch.mps.synchronize()

    @torch.inference_mode()
    def warmup(self, max_faces=4):
        """Compile expected person-count shapes before timing/starting a stream."""
        for count in range(1, max_faces+1):
            sample = dict(
                image=torch.zeros(1,1,3,self.image_size,self.image_size,device=self.device,dtype=self.dtype),
                heads=torch.zeros(1,1,count+1,3,224,224,device=self.device,dtype=self.dtype),
                head_bboxes=torch.zeros(1,1,count+1,4,device=self.device,dtype=self.dtype),
                num_valid_people=count)
            self.model(sample)
        self.sync()

    @torch.inference_mode()
    def process(self, image, max_faces=4, confidence=.6):
        self.sync()
        started = time.perf_counter()
        h, w = image.shape[:2]
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        resized = self.letterbox(rgb,640,stride=int(self.detector.stride.max()))[0]
        tensor = torch.from_numpy(resized.transpose(2,0,1).copy()).float()[None].to(self.device)/255
        predictions = self.detector(tensor)[0]
        detections = self.nms(predictions, confidence, .45)[0]
        detections[:,:4] = self.scale_coords(tensor.shape[2:], detections[:,:4], image.shape).round()
        detections = detections.cpu().numpy()
        head_class = self.detector.names.index('head')
        detections = [d for d in detections if int(d[-1]) == head_class and min(d[2]-d[0],d[3]-d[1]) >= 20]
        detections = sorted(detections,key=lambda d:(d[2]-d[0])*(d[3]-d[1]),reverse=True)[:max_faces]
        self.sync()
        detected = time.perf_counter()
        annotated, results = image.copy(), []
        if detections:
            boxes = torch.tensor(np.stack([d[:4] for d in detections]),dtype=torch.float32)
            # Same 10% head-box expansion as the official demonstration.
            widths, heights = boxes[:,2]-boxes[:,0], boxes[:,3]-boxes[:,1]
            boxes += torch.stack([-widths,-heights,widths,heights],1)*.1
            boxes[:,[0,2]] = boxes[:,[0,2]].clamp(0,w)
            boxes[:,[1,3]] = boxes[:,[1,3]].clamp(0,h)
            squared = self.square_bbox(boxes,w,h)
            pil = Image.fromarray(rgb)
            heads = torch.stack([TF.resize(TF.to_tensor(pil.crop(b.tolist())),[224,224],antialias=True) for b in squared])
            heads = TF.normalize(heads,self.mean,self.std)
            scene = TF.normalize(TF.resize(TF.to_tensor(pil),[self.image_size]*2,antialias=True),self.mean,self.std)
            normalized = squared / torch.tensor([w,h,w,h])
            sample = dict(image=scene[None,None].to(device=self.device,dtype=self.dtype),num_valid_people=len(detections),
                          heads=torch.cat([torch.zeros(1,3,224,224),heads])[None,None].to(device=self.device,dtype=self.dtype),
                          head_bboxes=torch.cat([torch.zeros(1,4),normalized])[None,None].to(device=self.device,dtype=self.dtype))
            _, vectors, heatmaps, inouts, *_ = self.model(sample)
            heatmaps = heatmaps[0,0,1:].float().cpu().numpy()
            vectors = vectors[0,0,1:].float().cpu().numpy()
            inouts = inouts.reshape(-1)[1:].float().sigmoid().cpu().numpy()
            if not all(np.isfinite(array).all() for array in (heatmaps, vectors, inouts)):
                raise ValueError('MTGS returned non-finite predictions; use float32')
            # Overlay heatmap for the largest detected head; arrows for all heads.
            hm = heatmaps[0]
            scaled = ((hm-hm.min()) / max(float(np.ptp(hm)),1e-9)*255).astype(np.uint8)
            if inouts[0] >= .8:
                colors = cv2.applyColorMap(cv2.resize(scaled,(w,h)),cv2.COLORMAP_TURBO)
                alpha = cv2.resize(scaled.astype(np.float32)/255,(w,h))[:,:,None]*.35
                annotated = (annotated*(1-alpha)+colors*alpha).astype(np.uint8)
            for i,(box,hm,vec,prob) in enumerate(zip(boxes.tolist(),heatmaps,vectors,inouts)):
                x1,y1,x2,y2 = map(int,box)
                start = ((x1+x2)//2,(y1+y2)//2)
                hy,hx = np.unravel_index(np.argmax(hm),hm.shape)
                target = (float(hx/hm.shape[1]),float(hy/hm.shape[0]))
                inside = float(prob) >= .8
                end = (round(target[0]*w),round(target[1]*h)) if inside else (round(start[0]+vec[0]*100),round(start[1]+vec[1]*100))
                color = (0,200,255) if inside else (220,100,230)
                cv2.rectangle(annotated,(x1,y1),(x2,y2),color,2)
                cv2.arrowedLine(annotated,start,end,color,2,cv2.LINE_AA,tipLength=.04)
                if inside:
                    cv2.circle(annotated,end,7,color,2)
                cv2.putText(annotated,f'{i+1}: {"in" if inside else "out"} {prob:.2f}',(x1,max(18,y1-7)),cv2.FONT_HERSHEY_SIMPLEX,.5,color,1)
                results.append(dict(bbox=box,head_confidence=float(detections[i][4]),
                                    target_xy_normalized=list(target) if inside else None,
                                    heatmap_peak_xy_normalized=list(target), in_frame_probability=float(prob),
                                    out_of_frame=not inside,gaze_vector=vec.tolist(),
                                    heatmap=hm.tolist(),arrow=[list(start),list(end)]))
        self.sync()
        finished = time.perf_counter()
        return annotated,dict(faces=results,detection_ms=(detected-started)*1000,
                              gaze_and_overlay_ms=(finished-detected)*1000,
                              pipeline_ms=(finished-started)*1000)
