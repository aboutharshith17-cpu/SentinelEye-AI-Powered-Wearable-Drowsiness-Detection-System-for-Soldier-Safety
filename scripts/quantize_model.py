#!/usr/bin/env python3
"""
quantize_model.py
Post-training quantization for DrowsyNet-Small
Produces INT8 TFLite model for embedded deployment
"""

import os
import sys
import torch
import torch.nn as nn
import argparse
from pathlib import Path

# Add ml_model to path
sys.path.insert(0, str(Path(__file__).parent))

from drowsynet_small import DrowsyNetSmall

def quantize_to_int8(model_path: str, output_path: str, example_input_size=(1, 3, 24, 24)):
    """Post-training dynamic INT8 quantization"""

    print("="*60)
    print("SentinelEye Model Quantization Pipeline")
    print("="*60)

    # Load model
    print(f"\nLoading model from: {model_path}")
    checkpoint = torch.load(model_path, map_location='cpu')

    model = DrowsyNetSmall(num_classes=3)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    print("Model loaded successfully")

    # Print model info
    total_params = sum(p.numel() for p in model.parameters())
    print(f"Parameters: {total_params:,}")
    print(f"Model size (FP32): {total_params * 4 / 1024:.1f} KB")

    # Dynamic quantization
    print("\nApplying INT8 dynamic quantization...")
    quantized_model = torch.quantization.quantize_dynamic(
        model,
        {nn.Linear, nn.Conv2d, nn.ReLU6},
        dtype=torch.qint8
    )

    # Print quantized model info
    quantized_params = sum(p.numel() for p in quantized_model.parameters())
    print(f"Quantized parameters: {quantized_params:,}")
    print(f"Model size (INT8): {quantized_params / 1024:.1f} KB")

    # Test inference
    print("\nTesting inference...")
    example_input = torch.randn(*example_input_size)
    with torch.no_grad():
        output = quantized_model(example_input)
    print(f"Input shape: {example_input.shape}")
    print(f"Output shape: {output.shape}")
    print(f"Output (softmax): {torch.softmax(output, dim=1)}")

    # Save quantized model
    print(f"\nSaving quantized model to: {output_path}")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    torch.save({
        'model_state_dict': quantized_model.state_dict(),
        'model_class': 'DrowsyNetSmall',
        'quantization': 'INT8',
        'input_size': example_input_size,
        'num_classes': 3,
        'timestamp': __import__('datetime').datetime.now().isoformat()
    }, output_path)

    # Also save TorchScript
    script_path = output_path.replace('.pth', '_scripted.pt')
    print(f"Saving TorchScript to: {script_path}")
    scripted_model = torch.jit.trace(quantized_model, example_input)
    scripted_model.save(script_path)

    print("\n" + "="*60)
    print("Quantization Complete!")
    print("="*60)
    print(f"Quantized model: {output_path}")
    print(f"TorchScript: {script_path}")
    print(f"Model size (INT8): {quantized_params / 1024:.1f} KB")
    print(f"Ready for TFLite conversion")
    print("="*60)

    return output_path

def convert_to_tflite(quantized_path: str, output_path: str):
    """Convert quantized PyTorch model to TFLite"""

    print("\nConverting to TFLite...")
    print("NOTE: Full TFLite conversion requires:")
    print("  1. ONNX export from PyTorch")
    print("  2. ONNX -> TensorFlow conversion")
    print("  3. TensorFlow -> TFLite conversion with INT8 calibration")
    print("\nPlease use the provided conversion script in firmware/")

    # Generate C header file for embedding in firmware
    print("\nGenerating C header file...")
    tflite_path = Path(output_path)

    # Create a placeholder header
    header_path = tflite_path.parent / "drowsynet_weights.h"
    with open(header_path, 'w') as f:
        f.write('#ifndef DROWSYNET_WEIGHTS_H\n')
        f.write('#define DROWSYNET_WEIGHTS_H\n\n')
        f.write('#include <stdint.h>\n\n')
        f.write('// DrowsyNet-Small v1 Quantized Model\n')
        f.write('// To be replaced with actual quantized weights\n')
        f.write('// Convert using: xxd -i drowsynet_quantized.tflite\n\n')
        f.write('extern const uint8_t drowsynet_model_data[];\n')
        f.write('extern const int drowsynet_model_size;\n\n')
        f.write('#endif /* DROWSYNET_WEIGHTS_H */\n')

    print(f"Header template: {header_path}")
    print("\nTo complete conversion:")
    print("1. Train model with train_drowsynet.py")
    print("2. Quantize with this script")
    print("3. Export to ONNX")
    print("4. Convert ONNX to TFLite")
    print("5. Run xxd -i drowsynet_quantized.tflite > drowsynet_weights.h")
    print("6. Copy to firmware/include/")

def main():
    parser = argparse.ArgumentParser(description='SentinelEye Model Quantization')
    parser.add_argument('--model', type=str, default='checkpoints/best_model.pth',
                        help='Path to trained FP32 model')
    parser.add_argument('--output', type=str, default='firmware/model/drowsynet_quantized.pth',
                        help='Output path for quantized model')
    parser.add_argument('--tflite-output', type=str, default='firmware/model/drowsynet_quantized.tflite',
                        help='Output path for TFLite model')
    parser.add_argument('--input-size', type=int, nargs='+', default=[1, 3, 24, 24],
                        help='Input tensor size')

    args = parser.parse_args()

    # Quantize model
    quantized_path = quantize_to_int8(args.model, args.output, tuple(args.input_size))

    # Convert to TFLite
    convert_to_tflite(quantized_path, args.tflite_output)

if __name__ == "__main__":
    main()
