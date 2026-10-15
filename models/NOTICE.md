# FoodCNN weight-model attribution

This release includes a CPU ONNX conversion of the published DeepWeightCNN
weight-only checkpoint from FoodCNN, by Ayoub Agouzoul, Georgy Salakhutdinov and
Georgii Kuznetsov, École Polytechnique, 2025.

- Source: https://github.com/FoodCNN/FoodCNN
- Source revision: `2c944166f988acff4374d131b8b1fe535a64abf6`
- Checkpoint: `src/02_weight_estimation/big_data_deepweightcnn_best.pth`
- Checkpoint SHA-256: `2ba124bdc113b36f2328015aa487dca018479fdbd5e175bb6facf4a56e0ce6fa`
- Export SHA-256: `ac53c053ee61861d58e74251ad582ccb8bd231ce26ff829a7e5e06e71057bdbd`
- Source inference contract: RGB, bilinear resize to 224×224, CHW float32 in
  [0, 1], no ImageNet normalization for the weight branch; output mass in grams.
- Conversion: float32, ONNX opset 13, fixed input `[1,3,224,224]`, CPU.
- The architecture and model weights are derived from upstream. The MIT license
  is included in `LICENSE_FoodCNN.txt`.

Upstream training used Nutrition5k, released by Google Research under CC BY 4.0:
https://github.com/google-research-datasets/Nutrition5k
Quin Thames, Arjun Karpur, Wade Norris, Fangting Xia, Liviu Panait, Tobias Weyand
and Jack Sim. *Nutrition5k: Towards Automatic Nutritional Understanding of Generic
Food*, CVPR 2021. https://arxiv.org/abs/2103.03375

The weight-only model predicts total dish weight. This release allocates that
prediction using Gemini's visual food shares. That allocation is an application
modification, not an upstream per-ingredient prediction. No upstream accuracy
claim is adopted for this app or for new smartphone/cuisine conditions.

Only the weight branch is included. Nutrition totals continue to use USDA data
and the user's reviewed portions. No public research photos are included here.
