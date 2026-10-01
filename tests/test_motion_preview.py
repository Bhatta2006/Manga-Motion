import tempfile
import unittest
import wave
from pathlib import Path
import numpy as np
from pipeline.layers.integrity import eligible_region, parallax_pose
from pipeline.motion.fixed import frames, assign_panel
from pipeline.adapters.sfx import materialize, samples, RATE


class MotionPreviewTests(unittest.TestCase):
    def test_protected_bubble_crossing_panel_edge(self):
        bubble=[180,5,240,50];panel=[10,20,200,150]
        for i in range(3):
            start,end,_=frames(panel,[bubble],[300,200],i)
            for step in range(101):
                t=step/100;b=[a+(z-a)*t for a,z in zip(start,end)]
                self.assertLessEqual(b[0],bubble[0]);self.assertLessEqual(b[1],bubble[1])
                self.assertGreaterEqual(b[2],bubble[2]);self.assertGreaterEqual(b[3],bubble[3])
            self.assertLessEqual(max((start[2]-start[0])/(end[2]-end[0]),(end[2]-end[0])/(start[2]-start[0])),1.4)

    def test_region_covers_original_at_every_phase(self):
        box=[40,40,100,130]
        for step in range(101):
            scale,dx,dy=parallax_pose(box,step/100)
            w,h=box[2]-box[0],box[3]-box[1]
            self.assertLessEqual(box[0]-(scale-1)*w/2+dx,box[0])
            self.assertGreaterEqual(box[2]+(scale-1)*w/2+dx,box[2])
            self.assertLessEqual(box[1]-(scale-1)*h/2+dy,box[1])
            self.assertGreaterEqual(box[3]+(scale-1)*h/2+dy,box[3])

    def test_region_rejects_texture_text_and_panel_edge(self):
        rgb=np.full((200,200,3),255,np.uint8);rgb[60:100,60:100]=0
        character=[60,60,100,100];panel=[0,0,200,200]
        region,reason=eligible_region(rgb,character,panel,[])
        self.assertIsNotNone(region);self.assertIsNone(reason)
        self.assertIsNone(eligible_region(rgb,character,panel,[[35,35,60,60]])[0])
        self.assertIsNone(eligible_region(rgb,character,[55,55,105,105],[])[0])
        rgb[48,48]=0
        self.assertIsNone(eligible_region(rgb,character,panel,[])[0])

    def test_sfx_pcm_and_repair_are_deterministic(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);asset=materialize(root,'wind');path=root/asset['file']
            before=path.read_bytes();path.write_bytes(b'corrupt')
            self.assertEqual(materialize(root,'wind'),asset);self.assertEqual(path.read_bytes(),before)
            with wave.open(str(path)) as f:
                self.assertEqual(f.getframerate(),RATE);self.assertEqual(f.getnchannels(),1)
            pcm=samples('wind');self.assertEqual(pcm[0],0);self.assertEqual(pcm[-1],0)
            self.assertGreater(np.sqrt(np.mean(pcm.astype(float)**2)),100)
            self.assertLessEqual(np.max(np.abs(pcm)),8192)

    def test_overflow_text_uses_maximum_overlap(self):
        self.assertEqual(assign_panel([80,10,160,80],[[0,0,100,100],[100,0,200,100]]),1)


if __name__=='__main__':unittest.main()
