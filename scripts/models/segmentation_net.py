import detectron2
from detectron2.engine import DefaultPredictor
from detectron2.config import get_cfg
from detectron2 import model_zoo
from detectron2.structures import ImageList

from detectron2.structures import Instances
import torch
import cv2 as cv


class seg:
    def __init__(self):
        self.cfg = get_cfg()
        # self.cfg.defrost()
        # self.cfg['MODEL']['ROI_HEADS']['SCORE_THRESH_TEST'] = 0.2
        # self.cfg['MODEL']['ROI_MASK_HEAD']['SCORE_THRESH_TEST'] = 0.2
        # add project-specific config (e.g., TensorMask) here if you're not running a model in detectron2's core library
        self.cfg.merge_from_file(model_zoo.get_config_file(
            "COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml"))
        self.cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.01  # set threshold for this model
        # Find a model from detectron2's model zoo. You can use the https://dl.fbaipublicfiles... url as well
        self.cfg.MODEL.WEIGHTS = model_zoo.get_checkpoint_url(
            "COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml")
        self.predictor = DefaultPredictor(self.cfg)

    def preprocess(self, original_image):

        with torch.no_grad():  # https://github.com/sphinx-doc/sphinx/issues/4258
            # Apply pre-processing to image.
            # if self.input_format == "RGB":
            #     # whether the model expects BGR inputs or RGB
            original_image = original_image[:, :, ::-1]
            height, width = original_image.shape[:2]
            image = self.predictor.aug.get_transform(
                original_image).apply_image(original_image)
            print(original_image.shape)
            print(image.shape)
            image = torch.as_tensor(image.astype("float32").transpose(2, 0, 1))
            print(image.shape)

            inputs = {"image": image.cuda(), "height": height, "width": width}
            return inputs

    def forward(self, image):
        with torch.no_grad():

            # scale = 1/1.333
            # preprocessed_image = self.preprocess(image)
            # images = ImageList.from_tensors(
            #     [torch.Tensor(image).permute(2, 0, 1)])  # preprocessed input tensor

            # instances = self.predictor.model.backbone(
            #     images.tensor.cuda())

            t_image = ImageList.from_tensors(
                [torch.Tensor(image).permute(2, 0, 1)])

            # print(image.shape)

            features = self.predictor.model.backbone(
                t_image.tensor.cuda())

            proposals, _ = self.predictor.model.proposal_generator(
                t_image, features)

            mask_features = [features[f]
                             for f in self.predictor.model.roi_heads.in_features]

            min_idx = -1
            ids = []
            for idx, (box, score) in enumerate(zip(proposals[0].proposal_boxes[:10], torch.sigmoid(proposals[0].objectness_logits[:10]))):
                # print(score)

                if score < 0.975:
                    break
                pts = box.detach().cpu().long()

                # if area is too big or if confidence is less than .95
                if ((pts[2] - pts[0]) * (pts[3] - pts[1]) / (image.shape[0]*image.shape[1]) > 0.3):
                    continue

                ids.append(idx)
                # cv.rectangle(image, (pts[0], pts[1]),
                #              (pts[2], pts[3]), (255, 0, 0))

                # print(score)

            mask_features = self.predictor.model.roi_heads.mask_pooler(
                mask_features, [proposals[0].proposal_boxes[ids]])

            # print(proposals[0].get_fields())
            new_prop = Instances(image.shape[:-1])
            new_prop.proposal_boxes = proposals[0].proposal_boxes[ids]
            new_prop.objectness_logits = proposals[0].objectness_logits[ids]
            # print(ids)
            instances, _ = self.predictor.model.roi_heads(
                t_image, features, [new_prop])

            # print(instances)

            return proposals[0].proposal_boxes[ids], mask_features, instances[0]