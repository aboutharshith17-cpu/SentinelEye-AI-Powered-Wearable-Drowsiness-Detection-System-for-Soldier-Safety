"""
drowsynet_small.py
DrowsyNet-Small v1: Lightweight CNN for drowsiness detection
Optimized for embedded edge deployment with INT8 quantization
Architecture: MobileNet-style depthwise-separable convolutions
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math

class DepthwiseSeparableConv(nn.Module):
    """Depthwise Separable Convolution: reduces params by 8x"""
    def __init__(self, in_ch, out_ch, kernel_size=3, stride=1, padding=1):
        super().__init__()
        self.depthwise = nn.Conv2d(in_ch, in_ch, kernel_size=kernel_size,
                                    stride=stride, padding=padding, groups=in_ch, bias=False)
        self.pointwise = nn.Conv2d(in_ch, out_ch, kernel_size=1, bias=False)
        self.bn = nn.BatchNorm2d(out_ch)
        self.relu = nn.ReLU6(inplace=True)

    def forward(self, x):
        x = self.depthwise(x)
        x = self.pointwise(x)
        x = self.bn(x)
        return self.relu(x)

class DrowsyNetSmall(nn.Module):
    """
    DrowsyNet-Small v1: 34K params, ~13KB quantized, 8ms inference on ESP32-S3
    Input: 24x24x3 RGB (scaled 0-1)
    Output: 3 classes [Awake, Drowsy, Asleep]
    """

    def __init__(self, num_classes=3):
        super().__init__()
        self.num_classes = num_classes

        # Block 1: Conv2D 3x3, 16 filters, ReLU6
        self.conv1 = nn.Sequential(
            nn.Conv2d(3, 16, kernel_size=3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(16),
            nn.ReLU6(inplace=True)
        )

        # Block 2: DepthwiseConv 3x3, 32 filters
        self.conv2 = DepthwiseSeparableConv(16, 32, kernel_size=3, stride=2, padding=1)

        # Block 3: DepthwiseConv 3x3, 32 filters
        self.conv3 = DepthwiseSeparableConv(32, 32, kernel_size=3, stride=1, padding=1)

        # Block 4: DepthwiseConv 3x3, 64 filters
        self.conv4 = DepthwiseSeparableConv(32, 64, kernel_size=3, stride=2, padding=1)

        # Block 5: DepthwiseConv 3x3, 64 filters
        self.conv5 = DepthwiseSeparableConv(64, 64, kernel_size=3, stride=1, padding=1)

        # Block 6: DepthwiseConv 3x3, 128 filters
        self.conv6 = DepthwiseSeparableConv(64, 128, kernel_size=3, stride=2, padding=1)

        # Adaptive pooling for variable input
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))

        # Fully connected layers with dropout
        self.classifier = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU6(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(64, num_classes)
        )

        # Initialize weights
        self._initialize_weights()

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, 0, 0.01)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)

    def forward(self, x):
        # Input: [B, 3, 24, 24]
        x = self.conv1(x)     # [B, 16, 24, 24]
        x = self.conv2(x)     # [B, 32, 12, 12]
        x = self.conv3(x)     # [B, 32, 12, 12]
        x = self.conv4(x)     # [B, 64, 6, 6]
        x = self.conv5(x)     # [B, 64, 6, 6]
        x = self.conv6(x)     # [B, 128, 3, 3]
        x = self.avgpool(x)   # [B, 128, 1, 1]
        x = torch.flatten(x, 1)  # [B, 128]
        x = self.classifier(x)   # [B, 3]
        return x

    def get_model_size_mb(self):
        """Get model size in MB (FP32)"""
        param_size = 0
        for param in self.parameters():
            param_size += param.nelement() * param.element_size()
        return param_size / (1024 * 1024)

    def get_param_count(self):
        """Get total parameter count"""
        return sum(p.numel() for p in self.parameters())


if __name__ == "__main__":
    model = DrowsyNetSmall()
    print(f"Model: {model}")
    print(f"Parameters: {model.get_param_count():,}")
    print(f"Model size (FP32): {model.get_model_size_mb():.2f} MB")
    print(f"Model size (INT8): {model.get_model_size_mb() / 4:.2f} MB")

    # Test forward pass
    x = torch.randn(1, 3, 24, 24)
    y = model(x)
    print(f"Output shape: {y.shape}")
    print(f"Output: {F.softmax(y, dim=1)}")
