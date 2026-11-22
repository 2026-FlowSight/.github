# RoundaboutHD:High-Resolution Real-World Urban Environment Benchmark for Multi-Camera Vehicle Tracking

## Dataset Contents

**Dataset je úplne ANOTOVANÝ, obsahuje detections aj TYPY karosérii už v sebe pre všetky autá, len si treba správne namapovať labels**
Pri práci s anotáciami môžu pomôcť moje skripty, nie sú spravené dôkladne ani moc komentované, ale dá sa inšpirovať ak vychádzame z predikcií, ktoré robí "old_demo".

**The dataset structure**:
```
RoundaboutHD/
├── kamera1/  ← Same structure applies to kamera2, kamera3, kamera4
│   ├── detection/
│   │   ├── labels_GT.zip/
│   │   │   ├── img000000.txt
│   │   │   ├── ...
│   │   │   └── img008999.txt  # Total: 9000 files
│   │   ├── labels_test.zip/
│   │   └── labels_xy.zip/
│   ├── SCT/
│   │   └── imagesc001_SCT_GT.txt
│   ├── geo-mapping/
│       ├── cam01_fitted_cam.json
│       ├── cam01_info.png
│       ├── cam01_topview.jpg
│       ├── cam01_trace.png
│       └── cam01_undistorted.png
│  
├── kamera2/
├── kamera3/
├── kamera4/
├── Multi_CAM_Ground_Truth.txt
└── vehicle_statistic.xlsx
```

## File/Directory Descriptions
---------------------------
- layout.jpg
    Layout image showing the geographic arrangement of the scene and camera placements.

- vehicle_statistic.xlsx
    Contextual information for each tracked vehicle (type, color, make, model) in SCT.

- Multi_CAM_Ground_Truth.txt
    Multi-camera tracking ground truth file. Format:
    {cam_num} {id_index} {frame_num} {x1:.2f} {y1:.2f} {width:.2f} {height:.2f} {xworld} {yworld}

- kameraX/detection/
    labels_GT.zip   : Manually inspected/corrected detection labels for each frame.
    labels_test.zip : Used for baseline experiments in the paper (SCT-based, excludes visible parking lot vehicles).
    labels_xy.zip   : Raw detection results from YOLOv12x.

- kameraXX/SCT/imagesc00x_SCT_GT.txt
    Ground truth for single-camera tracking.
    Format: {frame_id} {track_id} {bb[0]:.2f} {bb[1]:.2f} {bb[2]:.2f} {bb[3]:.2f} {cls}

- kameraXX/geo-mapping/
    Camera calibration and geometric transformation files for each camera, including fitted parameters
    and top/bird’s-eye view images. All transformations are computed using the CameraTransform Python package [1].


## Reference
---------
[1] Gerum, R. C., Richter, S., Winterl, A., Mark, C., Fabry, B., Le Bohec, C., & Zitterbart, D. P. (2019).
    CameraTransform: A Python package for perspective corrections and image mapping.
    SoftwareX, 10, 100333.
    https://doi.org/10.1016/j.softx.2019.100333
