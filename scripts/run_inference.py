#!/usr/bin/env python3
"""
run_inference.py
Run inference on test images for validation
Benchmarks model performance on ESP32-S3 and desktop
"""

import os
import sys
import time
import argparse
import numpy as np
from pathlib import Path

# Add ml_model to path
sys.path.insert(0, str(Path(__file__).parent.parent / "software" / "ml_model"))

import torch
import torch.nn as nn
from torchvision import transforms
from PIL import Image

from drowsynet_small import DrowsyNetSmall

class InferenceBenchmark:
    """Benchmark inference performance"""

    def __init__(self, model_path: str, device: str = 'cpu'):
        self.device = torch.device(device)
        self.model = self._load_model(model_path)
        self.model.eval()

        # Preprocessing
        self.transform = transforms.Compose([
            transforms.Resize((32, 32)),
            transforms.CenterCrop(28),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                std=[0.229, 0.224, 0.225])
        ])

        # Metrics
        self.inference_times = []
        self.confidences = []

    def _load_model(self, model_path: str):
        """Load trained model"""
        print(f"Loading model from: {model_path}")
        checkpoint = torch.load(model_path, map_location=self.device)
        model = DrowsyNetSmall(num_classes=3)
        model.load_state_dict(checkpoint['model_state_dict'])
        model = model.to(self.device)
        print(f"Model loaded: {sum(p.numel() for p in model.parameters()):,} parameters")
        return model

    def preprocess(self, image_path: str):
        """Preprocess image for inference"""
        img = Image.open(image_path).convert('RGB')
        img_tensor = self.transform(img).unsqueeze(0).to(self.device)
        return img_tensor

    def infer(self, image_path: str) -> dict:
        """Run inference on single image"""
        input_tensor = self.preprocess(image_path)

        with torch.no_grad():
            start_time = time.perf_counter()
            output = self.model(input_tensor)
            end_time = time.perf_counter()

        inference_time = (end_time - start_time) * 1000  # ms
        probabilities = torch.softmax(output, dim=1)
        confidence, prediction = torch.max(probabilities, 1)

        class_names = ['Awake', 'Drowsy', 'Asleep']
        result = {
            'class': class_names[prediction.item()],
            'confidence': confidence.item(),
            'inference_time_ms': inference_time,
            'probabilities': probabilities.cpu().numpy()[0].tolist()
        }

        self.inference_times.append(inference_time)
        self.confidences.append(confidence.item())

        return result

    def benchmark(self, n_iterations: int = 1000):
        """Benchmark inference speed"""
        print(f"\nRunning benchmark ({n_iterations} iterations)...")

        # Create dummy input
        dummy_input = torch.randn(1, 3, 28, 28).to(self.device)

        # Warmup
        with torch.no_grad():
            for _ in range(10):
                _ = self.model(dummy_input)

        # Benchmark
        times = []
        with torch.no_grad():
            for i in range(n_iterations):
                start = time.perf_counter()
                _ = self.model(dummy_input)
                end = time.perf_counter()
                times.append((end - start) * 1000)

                if (i + 1) % 100 == 0:
                    print(f"  Progress: {i + 1}/{n_iterations}")

        times = np.array(times)
        print(f"\nBenchmark Results:")
        print(f"  Mean:   {np.mean(times):.2f} ms")
        print(f"  Median: {np.median(times):.2f} ms")
        print(f"  Std:    {np.std(times):.2f} ms")
        print(f"  Min:    {np.min(times):.2f} ms")
        print(f"  Max:    {np.max(times):.2f} ms")
        print(f"  P95:    {np.percentile(times, 95):.2f} ms")
        print(f"  P99:    {np.percentile(times, 99):.2f} ms")

        return times

    def print_summary(self):
        """Print inference summary"""
        if not self.inference_times:
            print("No inference data available")
            return

        print(f"\nInference Summary:")
        print(f"  Total inferences: {len(self.inference_times)}")
        print(f"  Avg time: {np.mean(self.inference_times):.2f} ms")
        print(f"  Avg confidence: {np.mean(self.confidences):.3f}")
        print(f"  Min confidence: {np.min(self.confidences):.3f}")
        print(f"  Max confidence: {np.max(self.confidences):.3f}")

def main():
    parser = argparse.ArgumentParser(description='SentinelEye Inference Benchmark')
    parser.add_argument('--model', type=str, default='checkpoints/best_model.pth',
                        help='Path to trained model')
    parser.add_argument('--image', type=str, default=None,
                        help='Path to test image')
    parser.add_argument('--benchmark', action='store_true',
                        help='Run benchmark')
    parser.add_argument('--iterations', type=int, default=1000,
                        help='Number of benchmark iterations')
    parser.add_argument('--device', type=str, default='cpu',
                        help='Device (cpu/cuda)')

    args = parser.parse_args()

    # Initialize benchmark
    benchmark = InferenceBenchmark(args.model, args.device)

    # Run single inference
    if args.image and os.path.exists(args.image):
        print(f"\nRunning inference on: {args.image}")
        result = benchmark.infer(args.image)
        print(f"  Class: {result['class']}")
        print(f"  Confidence: {result['confidence']:.3f}")
        print(f"  Time: {result['inference_time_ms']:.2f} ms")
        print(f"  Probabilities: {result['probabilities']}")

    # Run benchmark
    if args.benchmark:
        times = benchmark.benchmark(args.iterations)
        benchmark.print_summary()

        # Compare with ESP32-S3
        print(f"\nESP32-S3 Performance Estimate:")
        esp32_factor = 15.0  # CPU is ~15x slower
        print(f"  Estimated ESP32-S3 time: {np.mean(times) * esp32_factor:.1f} ms")
        print(f"  Target: <10 ms per frame")
        if np.mean(times) * esp32_factor > 10:
            print("  WARNING: Model may be too slow for real-time on ESP32-S3")
            print("  Consider: smaller model, INT8 quantization, or more optimization")
        else:
            print("  OK: Model should run in real-time on ESP32-S3")

if __name__ == "__main__":
    main()
