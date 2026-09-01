"""YOLO Cloud Core — Training Pipeline.

Trains task classification and risk scoring models specifically for
YOLOv8-pose (COCO 17-keypoint) output. These models replace the
hardcoded heuristics in pose_engine.py with ML-trained classifiers
that match the quality of the MediaPipe core's models.
"""
