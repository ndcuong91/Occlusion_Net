# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved.
import torch
import numpy as np

from maskrcnn_benchmark.modeling.roi_heads.box_head.box_head import build_roi_box_head
from maskrcnn_benchmark.modeling.roi_heads.mask_head.mask_head import build_roi_mask_head
from maskrcnn_benchmark.modeling.roi_heads.keypoint_head.keypoint_head import build_roi_keypoint_head
from .graph_head.graph_head import build_roi_graph_head


class CombinedROIHeads(torch.nn.ModuleDict):
    """
    Combines a set of individual heads (for box prediction or masks) into a single
    head.
    """

    def __init__(self, cfg, heads):
        super(CombinedROIHeads, self).__init__(heads)
        self.cfg = cfg.clone()
        if cfg.MODEL.MASK_ON and cfg.MODEL.ROI_MASK_HEAD.SHARE_BOX_FEATURE_EXTRACTOR:
            self.mask.feature_extractor = self.box.feature_extractor
        if cfg.MODEL.KEYPOINT_ON and cfg.MODEL.ROI_KEYPOINT_HEAD.SHARE_BOX_FEATURE_EXTRACTOR:
            self.keypoint.feature_extractor = self.box.feature_extractor
        if cfg.MODEL.GRAPH_ON and cfg.MODEL.ROI_KEYPOINT_HEAD.SHARE_BOX_FEATURE_EXTRACTOR:
            self.graph.feature_extractor = self.box.feature_extractor

    def forward(self, features, proposals, targets=None):
        losses = {}
        # TODO rename x to roi_box_features, if it doesn't increase memory consumption
        x, detections, loss_box = self.box(features, proposals, targets)
        losses.update(loss_box)
        if self.cfg.MODEL.MASK_ON:
            mask_features = features
            # optimization: during training, if we share the feature extractor between
            # the box and the mask heads, then we can reuse the features already computed
            if (
                self.training
                and self.cfg.MODEL.ROI_MASK_HEAD.SHARE_BOX_FEATURE_EXTRACTOR
            ):
                mask_features = x
            # During training, self.box() will return the unaltered proposals as "detections"
            # this makes the API consistent during training and testing
            x, detections, loss_mask = self.mask(mask_features, detections, targets)
            losses.update(loss_mask)


        if self.cfg.MODEL.GRAPH_ON:
            graph_features = features
            # optimization: during training, if we share the feature extractor between
            # the box and the mask heads, then we can reuse the features already computed
            if (
                self.training
                and self.cfg.MODEL.ROI_GRAPH_HEAD.SHARE_BOX_FEATURE_EXTRACTOR
            ):
                graph_features = x
            # During training, self.box() will return the unaltered proposals as "detections"
            # this makes the API consistent during training and testing
            skip_detection=True
            if skip_detection:
                print('skip detection to get keypoint of whole input image')
                w,h = detections[0].size
                bbox_harcode = [[1,1,w-1,h-1]]
                detections[0].bbox = torch.from_numpy(np.asarray(bbox_harcode,dtype=np.float32))
                detections[0].extra_fields['scores']=torch.from_numpy(np.asarray([0.9],dtype=np.float32))
                detections[0].extra_fields['labels']=torch.from_numpy(np.asarray([1]))

            x, detections, loss_graph = self.graph(graph_features, detections, targets)
            losses.update(loss_graph)

        elif self.cfg.MODEL.KEYPOINT_ON:
            keypoint_features = features
            # optimization: during training, if we share the feature extractor between
            # the box and the mask heads, then we can reuse the features already computed
            if (
                self.training
                and self.cfg.MODEL.ROI_KEYPOINT_HEAD.SHARE_BOX_FEATURE_EXTRACTOR
            ):
                keypoint_features = x
            # During training, self.box() will return the unaltered proposals as "detections"
            # this makes the API consistent during training and testing
            x, detections, loss_keypoint = self.keypoint(keypoint_features, detections, targets)
            losses.update(loss_keypoint)




        return x, detections, losses




def build_roi_heads(cfg, in_channels):
    # individually create the heads, that will be combined together
    # afterwards
    roi_heads = []
    if cfg.MODEL.RETINANET_ON:
        return []

    if not cfg.MODEL.RPN_ONLY:
        roi_heads.append(("box", build_roi_box_head(cfg, in_channels)))
    if cfg.MODEL.MASK_ON:
        roi_heads.append(("mask", build_roi_mask_head(cfg, in_channels)))
    if cfg.MODEL.KEYPOINT_ON:
        roi_heads.append(("keypoint", build_roi_keypoint_head(cfg, in_channels)))
    if cfg.MODEL.KEYPOINT_ON and cfg.MODEL.GRAPH_ON:
        roi_heads.append(("graph", build_roi_graph_head(cfg, in_channels)))

    # combine individual heads in a single module
    if roi_heads:
        roi_heads = CombinedROIHeads(cfg, roi_heads)

    return roi_heads
